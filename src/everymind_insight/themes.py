"""Deterministic, versioned topic coding. No respondent text is exported publicly."""

import hashlib
import json
import re
from importlib.resources import files

from .schemas import Metric, MetricReference, Provenance, ThemeData, ThemeQuestion, ThemeSummary


def codebook():
    content = files("everymind_insight").joinpath("defaults/themes.json").read_bytes()
    return json.loads(content), hashlib.sha256(content).hexdigest()


def analyze_themes(frame, *, present_questions, input_hash, config_hash, source_record_numbers=None):
    book, book_hash = codebook()
    metrics, questions, review = [], [], []
    usable = frame.loc[frame.is_usable_id]
    provenance = Provenance(
        input_hash=input_hash, config_hash=config_hash, method="keyword_codebook",
        population="Usable response IDs with a nonblank answer to this comment question.",
        parameters={"codebook_version": book["version"], "codebook_hash": book_hash},
    )
    for question_id, spec in book["questions"].items():
        if question_id not in present_questions:
            continue
        comments = usable[question_id].dropna().astype(str).str.strip()
        comments = comments.loc[comments.ne("")]
        n = len(comments)
        dimensions = {"question": question_id}
        def add(identifier, value, definition, *, theme=None, share=False):
            metric = Metric(
                metric_id=identifier, dimensions={**dimensions, **({"theme": theme} if theme else {})},
                value=value / n if share and n else (None if share else value),
                numerator=value if share else None, denominator=n if share else None,
                n=n, unit="proportion" if share else "count", definition=definition,
                reason="no_nonblank_comments" if share and not n else None, provenance=provenance,
            )
            metrics.append(metric)
            return MetricReference(metric_id=metric.metric_id, dimensions=metric.dimensions)
        answered = add("comment_answered", n, "Usable respondents with a nonblank comment; blank comments are not counted as negative feedback.")
        counts = {theme["id"]: 0 for theme in spec["themes"]}
        matched = 0
        for index, comment in comments.items():
            text = " ".join(comment.casefold().split())
            tags = [theme["id"] for theme in spec["themes"] if any(re.search(pattern, text) for pattern in theme["patterns"])]
            matched += bool(tags)
            for tag in tags:
                counts[tag] += 1
            # Private source-row locator only; no comments, names or IDs copied.
            record = source_record_numbers[int(index)] if source_record_numbers is not None else int(index) + 2
            review.append({"source_record": record, "question": question_id, "theme_ids": tags})
        matched_ref = add("comment_coding_coverage", matched,
                          "Share of nonblank comments matching at least one keyword topic. This is not a coding-accuracy estimate.", share=True)
        unmatched_ref = add("comment_unclassified", n - matched,
                            "Nonblank comments matching no keyword topic; review in the private source workbook.")
        themes = []
        for theme in spec["themes"]:
            ref = add("theme_prevalence", counts[theme["id"]],
                      "Share of nonblank comments mentioning this codebook topic. Topics may overlap; a mention is not a sentiment or request classification.",
                      theme=theme["id"], share=True)
            themes.append(ThemeSummary(id=theme["id"], label=theme["label"], method="codebook", prevalence=[ref]))
        questions.append(ThemeQuestion(question_id=question_id, label=spec["label"], answered=answered,
                                       themes=themes, diagnostics=[matched_ref, unmatched_ref]))
    return metrics, ThemeData(status="available" if questions else "unavailable", questions=questions), review
