from pathlib import Path

import pytest
from pydantic import ValidationError

from everymind_insight.schemas import Metric, ReportBundle


def test_frontend_sample_matches_report_contract():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "report.sample.json"
    report = ReportBundle.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.schema_version == "1.0.0"
    assert report.generated_at.isoformat() == "2026-11-04T00:00:00+00:00"
    assert report.input_hash == "588f0b2bfcab3dbd79a45e20987aecf1906c677680a0a21dcbdc968094a4be19"
    assert report.data_kind == "synthetic"
    assert {metric.n for metric in report.metrics if metric.metric_id == "agree_after"
            and metric.dimensions["cohort"] == "all_responses"} == {450}
    assert report.findings and report.theme_data.questions and report.quality_report.metrics
    assert {metric.dimensions["skill"] for metric in report.metrics if metric.metric_id == "agree_after"} == {
        "identify_crises", "describe_988", "know_when_to_use_988",
    }

    calling = next(metric for metric in report.metrics if metric.metric_id == "calling_coverage")
    assert (calling.numerator, calling.denominator) == (108, 450)
    months = [metric for metric in report.metrics if metric.metric_id == "subgroup_response_count"]
    assert len(months) == 6 and sum(metric.suppressed for metric in months) == 2

    suppressed = next(metric for metric in report.metrics if metric.suppressed)
    with pytest.raises(ValidationError, match="Suppressed metrics must omit numeric fields"):
        Metric.model_validate({**suppressed.model_dump(), "n": 3})
