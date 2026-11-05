import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from everymind_insight.config import load_config
from everymind_insight.ingestion import ingest
from everymind_insight.normalization import normalize
from everymind_insight.quality import build_quality_report


SYNTHETIC_COMMENT = "Synthetic text with an address: case@example.test"


@pytest.fixture
def settings():
    return load_config()


@pytest.fixture
def rows():
    first = {
        "id": "synthetic-1",
        "start_time": "2026-10-19 10:00:00",
        "completion_time": "2026-10-19 10:00:20",
        "language": " English ",
        "roles": "School staff member;Caregiver/parent;School staff member;",
        "training_date": "2026-10-19",
        "county": "Montgomery County with NAMI MC",
        "identify_crises_after": "Strongly disagree",
        "describe_988_after": "Agree",
        "know_when_to_use_988_after": "Agree",
        "identify_crises_before": "Strongly agree",
        "describe_988_before": "Neither agree nor disagree",
        "know_when_to_use_988_before": "Disagree",
        "presenter_engaged": "Satisfied",
        "presenter_knew_subject": "Very agree",
        "presenter_organized": "Neither agree or disagree",
        "recommend_score": "5",
        "calling_score": "7",
        "valuable_comment": SYNTHETIC_COMMENT,
        "improve_comment": "More scenarios",
    }
    second = {
        **first,
        "id": "synthetic-2",
        "start_time": "2026-10-20 10:00:00",
        "completion_time": "2026-10-20 10:01:30",
        "language": "Spanish",
        "roles": "Student;",
        "training_date": "2026-10-20",
        "county": " Anne Arundel ",
        "presenter_engaged": "",
        "calling_score": "",
    }
    for key in second:
        if key.endswith(("_before", "_after")):
            second[key] = "Agree"
    return [first, second]


def write_survey(
    path: Path,
    settings,
    rows,
    *,
    columns=None,
    rename=None,
    blank_column=False,
):
    question_specs = settings.registry.questions
    columns = list(question_specs) if columns is None else columns
    rename = {} if rename is None else rename
    headers = [rename.get(key, question_specs[key].header) for key in columns]
    values = [[row.get(key) for key in columns] for row in rows]
    if blank_column:
        headers.append("")
        for row in values:
            row.append("")
    if path.suffix == ".xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = settings.registry.sheet
        sheet.append(headers)
        for row in values:
            sheet.append(row)
        workbook.save(path)
        workbook.close()
    else:
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(values)
    return path


def inspect(path, settings):
    incoming = ingest(path, settings.registry)
    normalized = normalize(incoming.frame, settings.normalization, settings.registry)
    return incoming, build_quality_report(normalized, settings.quality)


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_ingestion_and_normalization_for_both_formats(tmp_path, settings, rows, suffix):
    source = write_survey(tmp_path / f"baseline{suffix}", settings, rows)
    original = source.read_bytes()
    incoming, quality = inspect(source, settings)

    assert source.read_bytes() == original
    assert incoming.audit["input_row_count"] == 2
    assert incoming.audit["input_column_count"] == 20
    assert incoming.audit["missing_columns"] == []
    assert incoming.audit["new_columns"] == []
    assert incoming.audit["renamed_columns"] == []
    assert quality.frame.loc[0, "county_raw"] == "Montgomery County with NAMI MC"
    assert quality.frame.loc[0, "county"] == "Montgomery"
    assert quality.frame.loc[1, "county"] == "Anne Arundel"
    assert quality.frame.loc[0, "language"] == "English"
    assert quality.frame.loc[1, "language"] == "Spanish"
    assert quality.frame.loc[0, "roles"] == ("School staff member", "Caregiver/parent")
    assert quality.frame.loc[0, "identify_crises_after"] == 1
    assert quality.frame.loc[0, "presenter_engaged"] == 4
    assert quality.frame.loc[0, "presenter_knew_subject"] == 5
    assert quality.frame.loc[0, "presenter_organized"] == 3
    assert quality.frame.loc[0, "recommend_score"] == 5
    assert pd.isna(quality.frame.loc[1, "calling_score"])
    assert quality.frame.loc[0, "duration_seconds"] == 20
    assert quality.frame.loc[1, "duration_seconds"] == 90
    assert quality.report["flags"]["is_speeder"] == 1
    assert quality.report["flags"]["is_straightliner"] == 1
    assert quality.report["flags"]["is_large_reversal"] == 1
    assert quality.report["flags"]["is_flagged"] == 2
    flags_sensitivity = quality.report["objective_flag_sensitivity"]
    assert flags_sensitivity["all_responses"]["identify_crises"]["n"] == 2
    assert flags_sensitivity["excluding_flagged"]["identify_crises"]["n"] == 0
    assert flags_sensitivity["delta_excluding_minus_all"]["identify_crises"]["n"] == -2

    sensitivity = quality.report["presenter_sensitivity"]
    assert sensitivity["label"] == "Satisfied"
    assert sensitivity["objective_headlines_unchanged"] is True
    mappings = sensitivity["mappings"]
    configured = mappings["as_configured"]
    excluded = mappings["excluded"]
    assert configured["label_score"] == 4
    assert excluded["label_score"] is None
    assert configured["presenter_items"]["presenter_engaged"]["n_answered"] == 1
    assert configured["presenter_items"]["presenter_engaged"]["agree_count"] == 1
    assert excluded["presenter_items"]["presenter_engaged"]["n_answered"] == 0
    assert excluded["presenter_items"]["presenter_engaged"]["agree_count"] == 0
    assert configured["objective_headlines"] == excluded["objective_headlines"]
    assert SYNTHETIC_COMMENT not in json.dumps(quality.report)


def test_role_policy_changes_groups_without_changing_tokens(tmp_path, settings, rows):
    source = write_survey(tmp_path / "roles.csv", settings, rows)
    incoming = ingest(source, settings.registry)
    every = settings.normalization.model_copy(update={"role_policy": "every"})
    multiple = settings.normalization.model_copy(update={"role_policy": "multiple"})
    every_result = normalize(incoming.frame, every, settings.registry)
    multiple_result = normalize(incoming.frame, multiple, settings.registry)

    assert every_result.frame.loc[0, "role_groups"] == ("School staff member", "Caregiver/parent")
    assert multiple_result.frame.loc[0, "role_groups"] == ("Multiple roles",)
    assert every_result.frame["roles"].tolist() == multiple_result.frame["roles"].tolist()
    assert every_result.frame.loc[1, "role_groups"] == multiple_result.frame.loc[1, "role_groups"]


def test_invalid_values_are_audited_and_valid_columns_still_load(tmp_path, settings, rows):
    invalid = {
        **rows[0],
        "training_date": "October 40",
        "completion_time": "2026-10-19 09:59:59",
        "calling_score": "10.5",
        "recommend_score": "-1",
    }
    source = write_survey(tmp_path / "invalid.csv", settings, [invalid, rows[1]])
    _, quality = inspect(source, settings)

    assert pd.isna(quality.frame.loc[0, "training_date"])
    assert pd.isna(quality.frame.loc[0, "calling_score"])
    assert pd.isna(quality.frame.loc[0, "recommend_score"])
    assert quality.frame.loc[0, "county"] == "Montgomery"
    assert quality.report["flags"]["is_implausible_duration"] == 1
    assert quality.report["flags"]["is_speeder"] == 0
    assert quality.frame.loc[0, "training_date_raw"] == "October 40"


def append_refresh_rows(rows):
    return rows + [{**rows[1], "id": f"refresh-{number}"} for number in range(200)]


def inject_unknown_labels(row):
    return {
        **row,
        "county": "Anne Arundell",
        "roles": "New Community Partner;",
        "identify_crises_after": "Completely agree",
    }


def reword_identify_crises_header(settings):
    header = settings.registry.questions["identify_crises_after"].header
    return header.replace("mental health challenges and crises", "mental health concerns and crises")


def test_refresh_append_200_rows(tmp_path, settings, rows):
    baseline = write_survey(tmp_path / "baseline.csv", settings, rows)
    baseline_ingest = ingest(baseline, settings.registry)
    appended = write_survey(tmp_path / "appended.csv", settings, append_refresh_rows(rows))
    append_ingest, quality = inspect(appended, settings)

    assert append_ingest.audit["input_row_count"] == 202
    assert append_ingest.audit["schema_fingerprint"] == baseline_ingest.audit["schema_fingerprint"]
    assert append_ingest.audit["input_hash"] != baseline_ingest.audit["input_hash"]
    assert quality.report["n_usable"] == 202
    assert quality.report["objective_headlines"]["identify_crises"]["n"] == 202


def test_refresh_unseen_county_role_and_likert_labels(tmp_path, settings, rows):
    source = write_survey(tmp_path / "labels.csv", settings, [rows[0], inject_unknown_labels(rows[1])])
    incoming, quality = inspect(source, settings)

    assert incoming.audit["schema_fingerprint"] == incoming.audit["baseline_schema_fingerprint"]
    assert pd.isna(quality.frame.loc[1, "identify_crises_after"])
    assert quality.frame.loc[1, "identify_crises_after_raw"] == "Completely agree"
    assert quality.frame.loc[1, "county"] == "Anne Arundell"
    assert quality.frame.loc[1, "roles"] == ("New Community Partner",)
    columns = quality.report["normalization"]["columns"]
    assert columns["identify_crises_after"]["unmapped_values"] == {"Completely agree": 1}
    assert columns["county"]["suggestions"]["Anne Arundell"][0]["candidate"] == "Anne Arundel"
    assert columns["roles"]["unmapped_values"] == {"New Community Partner": 1}
    assert quality.report["objective_headlines"]["identify_crises"]["n"] == 1
    assert quality.report["objective_headlines"]["describe_988"]["n"] == 2


def test_refresh_blank_column(tmp_path, settings, rows):
    source = write_survey(tmp_path / "blank.csv", settings, rows, blank_column=True)
    incoming, quality = inspect(source, settings)

    assert incoming.audit["input_column_count"] == 21
    assert incoming.audit["blank_columns"] == [21]
    assert incoming.audit["new_columns"] == []
    assert incoming.audit["missing_columns"] == []
    assert quality.report["objective_headlines"]["identify_crises"]["n"] == 2


def test_refresh_reworded_question(tmp_path, settings, rows):
    source = write_survey(
        tmp_path / "reworded.csv",
        settings,
        rows,
        rename={"identify_crises_after": reword_identify_crises_header(settings)},
    )
    incoming, quality = inspect(source, settings)

    renamed = incoming.audit["renamed_columns"]
    assert [(item["question_id"], item["method"]) for item in renamed] == [("identify_crises_after", "fuzzy")]
    assert incoming.audit["missing_columns"] == []
    assert quality.frame["identify_crises_after"].tolist() == [1, 4]


def test_refresh_removed_column(tmp_path, settings, rows):
    columns = [key for key in settings.registry.questions if key != "calling_score"]
    source = write_survey(tmp_path / "removed.csv", settings, rows, columns=columns)
    incoming, quality = inspect(source, settings)

    assert incoming.audit["input_column_count"] == 19
    assert incoming.audit["missing_columns"] == ["calling_score"]
    assert incoming.frame["calling_score"].isna().all()
    assert quality.frame["calling_score"].isna().all()
    assert quality.report["objective_headlines"]["identify_crises"]["n"] == 2


def test_refresh_combined_changes_and_reordering(tmp_path, settings, rows):
    updated = append_refresh_rows(rows)
    updated[-1] = inject_unknown_labels(updated[-1])
    columns = list(settings.registry.questions)
    columns.remove("calling_score")
    columns.reverse()
    refreshed = write_survey(
        tmp_path / "refreshed.csv",
        settings,
        updated,
        columns=columns,
        rename={"identify_crises_after": reword_identify_crises_header(settings)},
        blank_column=True,
    )
    refresh_ingest, quality = inspect(refreshed, settings)

    assert refresh_ingest.audit["input_row_count"] == 202
    assert refresh_ingest.audit["input_column_count"] == 20
    assert refresh_ingest.audit["schema_fingerprint"] != refresh_ingest.audit["baseline_schema_fingerprint"]
    assert refresh_ingest.audit["missing_columns"] == ["calling_score"]
    assert refresh_ingest.audit["blank_columns"] == [20]
    assert refresh_ingest.audit["reordered_columns"]
    assert quality.frame["calling_score"].isna().all()
    assert quality.report["objective_headlines"]["identify_crises"]["n"] == 201
    assert quality.report["objective_headlines"]["describe_988"]["n"] == 202


@pytest.mark.parametrize(
    ("question_id", "old_text", "new_text"),
    [
        ("identify_crises_after", "I can ", ""),
        ("identify_crises_after", "I can ", "I can not "),
        ("calling_score", "call 988", "call 911"),
    ],
)
def test_semantically_changed_headers_are_sent_to_review(
    tmp_path, settings, rows, question_id, old_text, new_text
):
    question = settings.registry.questions[question_id].header
    source = write_survey(
        tmp_path / "changed.csv",
        settings,
        rows,
        rename={question_id: question.replace(old_text, new_text, 1)},
    )
    incoming = ingest(source, settings.registry)

    assert question_id in incoming.audit["missing_columns"]
    assert incoming.audit["review_columns"]
    assert incoming.frame[question_id].isna().all()
    assert incoming.frame["identify_crises_before"].notna().sum() == 2


def test_missing_and_duplicate_ids_are_flagged_without_deleting_rows(tmp_path, settings, rows):
    source = write_survey(
        tmp_path / "identity.csv",
        settings,
        [rows[0], rows[1], rows[0], {**rows[1], "id": ""}],
    )
    _, quality = inspect(source, settings)

    assert quality.report["n_rows"] == 4
    assert quality.report["n_usable"] == 1
    assert quality.report["flags"]["is_missing_id"] == 1
    assert quality.report["flags"]["is_duplicate_id"] == 2
    assert quality.report["objective_headlines"]["identify_crises"]["n"] == 1


def test_duplicate_header_is_reported_without_using_an_arbitrary_value(tmp_path, settings, rows):
    columns = list(settings.registry.questions) + ["recommend_score"]
    source = write_survey(tmp_path / "duplicate.csv", settings, rows, columns=columns)
    incoming = ingest(source, settings.registry)

    assert incoming.audit["duplicate_columns"]
    assert incoming.frame["recommend_score"].isna().all()
    assert "recommend_score" in incoming.audit["missing_columns"]
    assert incoming.frame.loc[0, "calling_score"] == "7"


def test_check_cli_writes_quality_report_without_comment_text(tmp_path, settings, rows):
    source = write_survey(tmp_path / "survey.xlsx", settings, rows)
    output = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "-m", "everymind_insight", "check", str(source), "--output", str(output)],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = output.read_text(encoding="utf-8")
    report = json.loads(payload)
    assert report["ingestion"]["input_row_count"] == 2
    assert report["presenter_sensitivity"]["objective_headlines_unchanged"] is True
    assert SYNTHETIC_COMMENT not in payload + result.stdout + result.stderr


def test_private_reference_workbook_phase1_quality_counts(survey_workbook, settings):
    incoming, quality = inspect(survey_workbook, settings)
    frame = quality.frame

    assert incoming.audit["input_row_count"] == 1299
    assert incoming.audit["input_column_count"] == 20
    assert incoming.audit["missing_columns"] == []
    assert frame["is_usable_id"].sum() == 1299
    counties = frame["county"].value_counts()
    assert counties.to_dict() == {
        "Anne Arundel": 937,
        "Prince George's": 309,
        "Montgomery": 34,
        "Queen Anne's": 12,
        "Fairfax": 6,
        "Harris": 1,
    }
    languages = frame["language"].value_counts()
    assert languages["English"] == 1280
    assert languages["Spanish"] == 19
    role_counts = Counter(role for roles in frame["roles"] for role in roles)
    assert role_counts["Student"] == 1080
    assert role_counts["Other"] == 95
    assert role_counts["Caregiver/parent"] == 71
    assert role_counts["School staff member"] == 68
    assert frame["training_date"].isna().sum() == 3
    assert frame["training_date"].nunique() == 46
    assert frame["duration_seconds"].min() == 10
    assert frame["duration_seconds"].max() == 8295
    assert frame["calling_score"].notna().sum() == 293
    assert frame.loc[frame["calling_score"].notna(), "training_date"].nunique() == 21
    assert frame["recommend_score"].isna().sum() == 33
    assert frame["recommend_score"].eq(5).sum() == 151
    assert quality.report["flags"] == {
        "is_missing_id": 0,
        "is_duplicate_id": 0,
        "is_speeder": 216,
        "is_impossible_timestamp": 0,
        "is_implausible_duration": 2,
        "is_invalid_timestamp": 0,
        "is_invalid_training_date": 0,
        "is_invalid_score": 0,
        "is_straightliner": 163,
        "is_large_reversal": 6,
        "is_flagged": 352,
    }
    combinations = {
        tuple(entry["flags"]): entry["n_rows"] for entry in quality.report["flag_combinations"]
    }
    assert combinations == {
        ("is_speeder",): 181,
        ("is_straightliner",): 129,
        ("is_speeder", "is_straightliner"): 34,
        ("is_large_reversal",): 5,
        ("is_implausible_duration",): 2,
        ("is_speeder", "is_large_reversal"): 1,
    }
    assert sum(combinations.values()) == 352
    assert quality.report["n_flag_assignments"] == 387
    objective_ids = [
        question_id
        for question_id in settings.registry.questions
        if question_id.endswith(("_before", "_after"))
    ]
    objective_scores = frame[objective_ids]
    assert objective_scores.eq(1).all(axis=1, skipna=False).sum() == 17
    assert objective_scores.eq(5).all(axis=1, skipna=False).sum() == 81
    assert frame["valuable_comment"].notna().sum() == 1063
    assert frame["improve_comment_raw"].notna().sum() == 652
    assert frame["improve_comment"].notna().sum() == 651
    improve = quality.report["normalization"]["columns"]["improve_comment"]
    assert improve["n_raw_non_null"] == 652
    assert improve["n_whitespace_only"] == 1
    assert quality.report["presenter_sensitivity"]["objective_headlines_unchanged"] is True

    uncollected_sessions = frame["training_date"].isin(
        [datetime(2026, 10, 20), datetime(2026, 10, 21)]
    )
    assert uncollected_sessions.any()
    presenter = ["presenter_engaged", "presenter_knew_subject", "presenter_organized"]
    assert frame.loc[uncollected_sessions, presenter].isna().all().all()
