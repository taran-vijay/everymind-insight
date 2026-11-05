"""Load survey exports and audit their headers against the approved registry."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet
from rapidfuzz.fuzz import ratio

from .config import QuestionSpec, SurveyRegistry


_HEADER_WORD = re.compile(r"[^\W_]+")
_NEGATION = re.compile(r"\b(?:no|not|never|cannot|can t|won t|don t|doesn t|didn t|isn t|wasn t)\b")
_NUMBER = re.compile(r"\b\d+\b")
_PAST_CONTEXT = re.compile(r"\b(?:think back|before|prior to|pre training)\b")
_PRESENT_CONTEXT = re.compile(r"\b(?:after (?:the |this |your )?training|post training|currently|today|now)\b")
_PRESENT_STATEMENT = re.compile(r"\b(?:i|you) (can|know|understand|(?:am|are) able to|feel able to)\b")
_PAST_STATEMENT = re.compile(r"\b(?:i|you) (could|knew|understood|(?:was|were) able to|felt able to)\b")
_PAST_TO_PRESENT = {
    "could": "can", "knew": "know", "understood": "understand",
    "was able to": "am able to", "were able to": "are able to", "felt able to": "feel able to",
}


@dataclass(frozen=True)
class IngestedSurvey:
    """Canonical raw cells in memory and a local schema audit."""

    frame: pd.DataFrame
    audit: dict[str, Any]


def _read_xlsx(source: bytes, sheet: str) -> tuple[list[Any], list[list[Any]]]:
    try:
        # Use actual stored cells instead of trusting the sheet's declared dimensions.
        workbook = load_workbook(io.BytesIO(source), data_only=True)
    except (BadZipFile, InvalidFileException, IndexError, KeyError, OSError, SyntaxError, ValueError) as error:
        raise ValueError("The input is not a readable .xlsx workbook.") from error

    try:
        if sheet not in workbook.sheetnames:
            raise ValueError(f"The workbook does not contain the expected worksheet {sheet!r}.")
        worksheet = workbook[sheet]
        if not isinstance(worksheet, Worksheet):
            raise ValueError(f"The workbook sheet {sheet!r} does not contain a table of cells.")
        records = worksheet.iter_rows(values_only=True)
        headers = list(next(records, ()))
        rows = [list(row) for row in records]
    finally:
        workbook.close()

    return headers, rows


def _read_csv(source: bytes) -> tuple[list[Any], list[list[Any]]]:
    with io.TextIOWrapper(io.BytesIO(source), encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        try:
            headers = next(reader, [])
            rows = []
            for row in reader:
                if row and len(row) != len(headers):
                    raise ValueError(
                        f"CSV record ending on line {reader.line_num} has {len(row)} fields. "
                        f"The header has {len(headers)} fields."
                    )
                rows.append(row)
        except UnicodeDecodeError as error:
            raise ValueError("Save the CSV with UTF-8 encoding and try again.") from error
        except csv.Error as error:
            raise ValueError(f"Invalid CSV record near line {reader.line_num}.") from error

    return headers, rows


def _normalize_header(header: str | None) -> str:
    if header is None:
        return ""
    text = unicodedata.normalize("NFKC", header).casefold()
    return " ".join(_HEADER_WORD.findall(text)) or text.strip()


def _fingerprint(headers: list[str | None]) -> str:
    encoded = json.dumps(headers, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _objective_signature(text: str) -> tuple[str | None, str | None]:
    # The source workbook says "Now think back to before..." on recalled items.
    context = text.replace("now think back", "think back")
    past = _PAST_STATEMENT.search(text)
    present = _PRESENT_STATEMENT.search(text)
    has_past = past is not None or _PAST_CONTEXT.search(context) is not None
    has_present = present is not None or _PRESENT_CONTEXT.search(context) is not None
    if has_past == has_present:
        return None, None
    if past is not None:
        return "before", f"{_PAST_TO_PRESENT[past.group(1)]} {text[past.end():].strip()}"
    if present is not None:
        return "after", text[present.start(1):]
    # Explicit timing can help with reordered wording, but a missing skill stem
    # must not match on a common survey instruction alone.
    return ("before" if has_past else "after"), text


def _fuzzy_scores(
    header: str, registry: SurveyRegistry
) -> tuple[list[tuple[str, float]], float]:
    eligible = []
    nearest = 0.0
    timing, stem = _objective_signature(header)
    negated = _NEGATION.search(header) is not None
    numbers = set(_NUMBER.findall(header))
    for question_id, question in registry.questions.items():
        if not question.fuzzy:
            continue
        scores = []
        for expected in (question.header, *question.aliases):
            expected_key = _normalize_header(expected)
            full_score = ratio(header, expected_key)
            nearest = max(nearest, full_score)
            if negated != (_NEGATION.search(expected_key) is not None):
                continue
            if numbers != set(_NUMBER.findall(expected_key)):
                continue
            if question.objective_skill is not None or question.objective_timing is not None:
                _, expected_stem = _objective_signature(expected_key)
                if timing != question.objective_timing or stem is None or expected_stem is None:
                    continue
                stem_score = ratio(stem, expected_stem)
                if stem_score < registry.fuzzy_threshold:
                    continue
                scores.append(0.4 * full_score + 0.6 * stem_score)
            else:
                scores.append(full_score)
        if scores:
            eligible.append((question_id, max(scores)))
    return sorted(eligible, key=lambda candidate: (-candidate[1], candidate[0])), nearest


def _match_headers(headers: list[str | None], registry: SurveyRegistry) -> dict[str, Any]:
    positions_by_name: dict[str, list[int]] = defaultdict(list)
    blank_positions = []
    for position, header in enumerate(headers, start=1):
        key = _normalize_header(header)
        if key:
            positions_by_name[key].append(position)
        else:
            blank_positions.append(position)

    expected_ids: dict[str, set[str]] = defaultdict(set)
    for question_id, question in registry.questions.items():
        for expected in (question.header, *question.aliases):
            expected_ids[_normalize_header(expected)].add(question_id)

    matches = []
    new = []
    duplicates = []
    review = []
    pending = {}
    exact_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    blocked = set()
    for name, positions in positions_by_name.items():
        ids = expected_ids.get(name, set())
        entries = [{"position": position, "header": headers[position - 1]} for position in positions]
        if len(positions) > 1:
            blocked.update(ids)
            duplicates.extend(entries)
        elif len(ids) > 1:
            blocked.update(ids)
            review.append({**entries[0], "reason": "registry_alias_collision", "candidates": sorted(ids)})
        elif ids:
            question_id = next(iter(ids))
            exact_by_id[question_id].append(entries[0])
        else:
            pending[name] = entries[0]

    for question_id, entries in exact_by_id.items():
        if len(entries) > 1 or question_id in blocked:
            blocked.add(question_id)
            review.extend(
                {**entry, "reason": "multiple_columns_for_question", "question_id": question_id}
                for entry in entries
            )
            continue
        entry = entries[0]
        question = registry.questions[question_id]
        method = "exact" if _normalize_header(entry["header"]) == _normalize_header(question.header) else "alias"
        matches.append(_match_entry(entry, question_id, question, method, 100.0))

    exact_ids = {entry["question_id"] for entry in matches}
    fuzzy_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for name, entry in pending.items():
        ranked, nearest = _fuzzy_scores(name, registry)
        if not ranked or ranked[0][1] < registry.fuzzy_threshold:
            if nearest >= registry.fuzzy_threshold:
                review.append({**entry, "reason": "question_meaning_or_timing_unclear"})
            else:
                new.append(entry)
            continue

        question_id, score = ranked[0]
        if len(ranked) > 1 and score - ranked[1][1] <= registry.fuzzy_margin:
            review.append({**entry, "reason": "fuzzy_candidates_too_close", "candidates": [question_id, ranked[1][0]]})
        elif question_id in blocked or question_id in exact_ids:
            review.append({**entry, "reason": "question_already_claimed", "question_id": question_id})
        else:
            fuzzy_by_id[question_id].append(
                _match_entry(entry, question_id, registry.questions[question_id], "fuzzy", score)
            )

    for question_id, entries in fuzzy_by_id.items():
        if len(entries) > 1:
            review.extend({**entry, "reason": "multiple_columns_for_question"} for entry in entries)
        else:
            matches.append(entries[0])

    def position_of(entry: dict[str, Any]) -> int:
        return entry["position"]

    matches.sort(key=position_of)
    present = [entry["question_id"] for entry in matches]
    missing = [question_id for question_id in registry.questions if question_id not in present]
    expected_order = [question_id for question_id in registry.questions if question_id in present]
    return {
        "matches": matches,
        "present_columns": present,
        "missing_columns": missing,
        "new_columns": sorted(new, key=position_of),
        "blank_columns": blank_positions,
        "duplicate_columns": sorted(duplicates, key=position_of),
        "review_columns": sorted(review, key=position_of),
        "renamed_columns": [entry for entry in matches if entry["header"] != entry["expected_header"]],
        "reordered_columns": [entry for entry, expected in zip(matches, expected_order) if entry["question_id"] != expected],
    }


def _match_entry(
    entry: dict[str, Any], question_id: str, question: QuestionSpec, method: str, score: float
) -> dict[str, Any]:
    return {
        **entry,
        "question_id": question_id,
        "expected_header": question.header,
        "method": method,
        "score": round(score, 2),
    }


def _blank_cell(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def ingest(path: str | Path, registry: SurveyRegistry, *, sheet: str | None = None) -> IngestedSurvey:
    """Load an XLSX or UTF-8 CSV without changing the source bytes."""
    input_path = Path(path)
    suffix = input_path.suffix.casefold()
    if suffix not in {".xlsx", ".csv"}:
        raise ValueError("The survey input must be an .xlsx workbook or a .csv file.")

    source = input_path.read_bytes()
    worksheet = (sheet or registry.sheet) if suffix == ".xlsx" else None
    if worksheet is None:
        source_headers, source_rows = _read_csv(source)
    else:
        source_headers, source_rows = _read_xlsx(source, worksheet)

    data_width = max((len(row) for row in source_rows), default=0)
    width = max(len(source_headers), data_width)
    headers = [str(header) if header is not None else None for header in source_headers]
    headers.extend([None] * (width - len(headers)))
    if not any(_normalize_header(header) for header in headers):
        raise ValueError("The survey input does not contain a named header row.")
    rows = [row for row in source_rows if not all(_blank_cell(value) for value in row)]
    raw = pd.DataFrame(rows, columns=range(width), dtype=object)

    audit = _match_headers(headers, registry)
    by_id = {entry["question_id"]: entry["position"] - 1 for entry in audit["matches"]}
    frame = pd.DataFrame(index=raw.index)
    for question_id in registry.questions:
        frame[question_id] = raw[by_id[question_id]] if question_id in by_id else pd.NA

    audit.update({
        "input_hash": hashlib.sha256(source).hexdigest(),
        "schema_fingerprint": _fingerprint(headers),
        "baseline_schema_fingerprint": _fingerprint([question.header for question in registry.questions.values()]),
        "input_row_count": len(rows),
        "input_column_count": width,
        "blank_row_count": len(source_rows) - len(rows),
        "worksheet": worksheet,
    })
    return IngestedSurvey(frame=frame, audit=audit)
