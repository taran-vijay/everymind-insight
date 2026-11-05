"""Normalize canonical survey columns and retain the original values in memory."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from numbers import Real
import unicodedata

import pandas as pd
import pandera.pandas as pa
from rapidfuzz import fuzz, process

from .config import COMMENT_ITEMS, PRESENTER_ITEMS, SCORE_ITEMS, NormalizationConfig, SurveyRegistry


@dataclass(frozen=True)
class NormalizationResult:
    frame: pd.DataFrame
    diagnostics: dict
    objective_columns: dict[str, dict[str, str]]
    sensitivity_label: str
    sensitivity_score: int | None
    sensitivity_masks: dict[str, pd.Series]


def _label(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _display(value: object) -> str | None:
    if pd.isna(value):
        return None
    return str(value).strip() or None


def _id(value: object) -> str | None:
    if isinstance(value, Real) and not pd.isna(value) and float(value).is_integer():
        return str(int(value))
    return _display(value)


def _aliases(aliases: dict) -> dict:
    return {_label(label): value for label, value in aliases.items()}


def _counts(values) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _answer_mask(series: pd.Series) -> pd.Series:
    return series.map(lambda value: _display(value) is not None)


def _column_counts(raw: pd.Series, clean: pd.Series, present: pd.Series) -> dict:
    clean_present = clean.notna()
    if raw.name == "roles":
        clean_present = clean.map(bool)
    changed = [
        before != after
        for before, after in zip(raw[present & clean_present], clean[present & clean_present])
    ]
    whitespace_only = raw.map(
        lambda value: isinstance(value, str) and bool(value) and not value.strip()
    )
    return {
        "n_raw_non_null": int(raw.notna().sum()),
        "n_raw_answered": int(present.sum()),
        "n_whitespace_only": int(whitespace_only.sum()),
        "n_clean_answered": int(clean_present.sum()),
        "n_missing": int((~present).sum()),
        "n_invalid": int((present & ~clean_present).sum()),
        "n_changed": sum(bool(value) for value in changed),
    }


def _categorical(raw: pd.Series, aliases: dict[str, str]) -> tuple[pd.Series, dict]:
    normalized = _aliases(aliases)
    unmapped = Counter()

    def clean_value(value: object) -> str | None:
        display = _display(value)
        if display is None:
            return None
        key = _label(display)
        if key in normalized:
            return normalized[key]
        unmapped[str(value)] += 1
        return " ".join(display.split())

    clean = raw.map(clean_value).astype("string")
    return clean, {
        "unmapped_values": dict(sorted(unmapped.items())),
        "value_counts": _counts(clean.dropna()),
    }


def _county(raw: pd.Series, config: NormalizationConfig) -> tuple[pd.Series, dict]:
    clean, diagnostics = _categorical(raw, config.county_aliases)
    candidates = {
        candidate: _label(candidate) for candidate in sorted(set(config.county_aliases.values()))
    }
    diagnostics["suggestions"] = {
        value: [
            {"candidate": candidate, "score": round(score, 1)}
            for _, score, candidate in process.extract(
                _label(value),
                candidates,
                scorer=fuzz.WRatio,
                score_cutoff=config.county_suggestion_threshold,
                limit=3,
            )
        ]
        for value in diagnostics["unmapped_values"]
    }
    return clean, diagnostics


def _roles(raw: pd.Series, config: NormalizationConfig) -> tuple[pd.Series, dict]:
    normalized = _aliases(config.role_aliases)
    unmapped = Counter()
    repeated = normalized_tokens = empty_tokens = 0

    def clean_roles(value: object) -> tuple[str, ...]:
        nonlocal repeated, normalized_tokens, empty_tokens
        display = _display(value)
        if display is None:
            return ()
        tokens = []
        seen = set()
        for raw_token in display.split(";"):
            token = " ".join(raw_token.split())
            if not token:
                empty_tokens += 1
                continue
            key = _label(token)
            canonical = normalized.get(key)
            if canonical is None:
                unmapped[raw_token] += 1
                canonical = token
            normalized_tokens += raw_token != canonical
            canonical_key = _label(canonical)
            if canonical_key in seen:
                repeated += 1
                continue
            seen.add(canonical_key)
            tokens.append(canonical)
        return tuple(tokens)

    clean = raw.map(clean_roles)
    return clean, {
        "unmapped_values": dict(sorted(unmapped.items())),
        "token_counts": _counts(token for tokens in clean for token in tokens),
        "n_multi_role": int(clean.map(len).gt(1).sum()),
        "n_repeated_tokens_removed": repeated,
        "n_empty_tokens_removed": empty_tokens,
        "n_normalized_tokens": normalized_tokens,
        "role_policy": config.role_policy,
    }


def _role_group(tokens: tuple[str, ...]) -> str | None:
    if len(tokens) > 1:
        return "Multiple roles"
    return tokens[0] if tokens else None


def _parse_date(value: object, formats: list[str], *, date_only: bool) -> pd.Timestamp:
    if isinstance(value, (datetime, date)) and not pd.isna(value):
        parsed = value
    else:
        text = _display(value)
        if text is None:
            return pd.NaT
        for date_format in formats:
            try:
                parsed = datetime.strptime(text, date_format)
                break
            except ValueError:
                continue
        else:
            return pd.NaT
    try:
        stamp = pd.Timestamp(parsed)
        if date_only:
            return pd.Timestamp(stamp.date()).as_unit("ns")
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert("UTC").tz_localize(None)
        return stamp.as_unit("ns")
    except (ValueError, OverflowError):
        return pd.NaT


def _dates(raw: pd.Series, formats: list[str], *, date_only: bool) -> pd.Series:
    return pd.to_datetime(raw.map(lambda value: _parse_date(value, formats, date_only=date_only)))


def _likert(raw: pd.Series, aliases: dict[str, int]) -> tuple[pd.Series, dict]:
    display = raw.map(_display).astype("string")
    clean = display.map(lambda value: aliases.get(_label(value)), na_action="ignore")
    clean = clean.astype("Int64")
    unmapped = raw[display.notna() & clean.isna()]
    return clean, {"unmapped_values": _counts(str(value) for value in unmapped)}


def _score(raw: pd.Series) -> pd.Series:
    numbers = pd.to_numeric(raw.map(_display), errors="coerce")
    bounded = numbers.where(numbers.between(0, 10))
    return bounded.where(bounded.mod(1).eq(0)).astype("Int64")


def _schema(objective_ids: set[str]) -> pa.DataFrameSchema:
    columns = {
        field: pa.Column(pd.StringDtype(), nullable=True)
        for field in ("id", "county", "language", "role_group", *COMMENT_ITEMS)
    }
    columns.update(
        {field: pa.Column(pa.DateTime, nullable=True) for field in ("training_date", "start_time", "completion_time")}
    )
    for field in ("roles", "role_groups"):
        columns[field] = pa.Column(
            object, pa.Check(lambda values: values.map(lambda value: isinstance(value, tuple)))
        )
    columns.update(
        {
            field: pa.Column(pd.Int64Dtype(), pa.Check.in_range(1, 5), nullable=True)
            for field in (*sorted(objective_ids), *PRESENTER_ITEMS)
        }
    )
    columns.update(
        {field: pa.Column(pd.Int64Dtype(), pa.Check.in_range(0, 10), nullable=True) for field in SCORE_ITEMS}
    )
    return pa.DataFrameSchema(columns)


def normalize(
    raw: pd.DataFrame, config: NormalizationConfig, registry: SurveyRegistry
) -> NormalizationResult:
    """Build a typed canonical frame and private diagnostics without changing the source."""
    objective_columns = {}
    for field, question in registry.questions.items():
        if question.objective_skill and question.objective_timing:
            objective_columns.setdefault(question.objective_skill, {})[question.objective_timing] = field
    objective_ids = {field for pair in objective_columns.values() for field in pair.values()}
    source = raw.reindex(columns=list(registry.questions), fill_value=pd.NA)
    clean = pd.DataFrame(index=source.index)
    columns = {}
    likert_aliases = _aliases(config.likert_aliases)
    presenter_aliases = likert_aliases | _aliases(config.presenter_likert_aliases)
    sensitivity_label = config.presenter_sensitivity_label
    sensitivity_key = _label(sensitivity_label)
    sensitivity_masks = {}

    for field in source.columns:
        values = source[field]
        diagnostics = {}
        if field == "id":
            normalized = values.map(_id).astype("string")
        elif field == "county":
            normalized, diagnostics = _county(values, config)
        elif field == "roles":
            normalized, diagnostics = _roles(values, config)
        elif field == "language":
            normalized, diagnostics = _categorical(values, config.language_aliases)
        elif field == "training_date":
            normalized = _dates(values, config.date_formats, date_only=True)
        elif field in ("start_time", "completion_time"):
            normalized = _dates(values, config.timestamp_formats, date_only=False)
        elif field in objective_ids:
            normalized, diagnostics = _likert(values, likert_aliases)
        elif field in PRESENTER_ITEMS:
            normalized, diagnostics = _likert(values, presenter_aliases)
            sensitivity_masks[field] = values.map(
                lambda value: _display(value) is not None and _label(str(value)) == sensitivity_key
            ).astype(bool)
        elif field in SCORE_ITEMS:
            normalized = _score(values)
        else:
            normalized = values.map(_display).astype("string")
        clean[field] = normalized
        columns[field] = _column_counts(values, normalized, _answer_mask(values)) | diagnostics

    clean["role_group"] = clean["roles"].map(_role_group).astype("string")
    if config.role_policy == "every":
        clean["role_groups"] = clean["roles"]
    else:
        clean["role_groups"] = clean["role_group"].map(
            lambda group: () if pd.isna(group) else (group,)
        )
    columns["roles"]["group_counts"] = _counts(
        group for groups in clean["role_groups"] for group in groups
    )
    clean = _schema(objective_ids).validate(clean)
    frame = pd.concat([clean, source.add_suffix("_raw")], axis=1)
    return NormalizationResult(
        frame,
        {"columns": columns},
        objective_columns,
        sensitivity_label,
        presenter_aliases.get(sensitivity_key),
        sensitivity_masks,
    )
