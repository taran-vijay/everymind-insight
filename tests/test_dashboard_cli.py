import json
from pathlib import Path

from typer.testing import CliRunner

from everymind_insight.cli import app


SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "report.sample.json"


def test_dashboard_defaults_copy_the_sample_unchanged(tmp_path, monkeypatch):
    report = tmp_path / "fixtures" / "report.sample.json"
    report.parent.mkdir()
    content = SAMPLE.read_bytes()
    report.write_bytes(content)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["dashboard"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "dashboard" / "report.json").read_bytes() == content


def test_dashboard_replaces_the_report_with_the_selected_bundle(tmp_path):
    report = tmp_path / "chosen.json"
    content = json.dumps(json.loads(SAMPLE.read_bytes()), separators=(",", ":")).encode()
    report.write_bytes(content)
    out = tmp_path / "dashboard"
    out.mkdir()
    destination = out / "report.json"
    destination.write_text("old", encoding="utf-8")

    result = CliRunner().invoke(app, ["dashboard", "--report", str(report), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert destination.read_bytes() == content
    assert sorted(path.name for path in out.iterdir()) == ["report.json"]


def test_dashboard_rejects_a_numeric_value_in_a_suppressed_cell(tmp_path):
    bundle = json.loads(SAMPLE.read_bytes())
    metric = next(metric for metric in bundle["metrics"] if metric["suppressed"])
    metric["value"] = 123456789
    report = tmp_path / "invalid.json"
    report.write_text(json.dumps(bundle), encoding="utf-8")
    out = tmp_path / "dashboard"
    out.mkdir()
    destination = out / "report.json"
    destination.write_text("old", encoding="utf-8")

    result = CliRunner().invoke(app, ["dashboard", "--report", str(report), "--out", str(out)])

    assert result.exit_code == 1
    assert "valid public report bundle" in result.output
    assert "123456789" not in result.output
    assert destination.read_text(encoding="utf-8") == "old"
