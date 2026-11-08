"""Tests for actual exports, release protection, coding and website packaging."""
import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from everymind_insight.cli import app
from everymind_insight.config import load_config
from everymind_insight.pages import prepare_pages
from everymind_insight.release import validate_release
from everymind_insight.reporting import build_report
from everymind_insight.schemas import ReportBundle

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = 'private-person@example.test'


def export(path, *, missing=(), flagged=False, count=80):
    config = load_config()
    keys = [key for key in config.registry.questions if key not in missing]
    rows = []
    for i in range(count):
        row = dict.fromkeys(keys, '')
        row.update(id=f'{PRIVATE}-{i}', start_time='2026-10-19 10:00:00',
                   completion_time='2026-10-19 10:02:00',
                   training_date='2026-10-19' if i % 2 else '2026-09-20',
                   county="Anne Arundel" if i % 2 else "Prince George's",
                   language='English', roles='Student' if i % 2 else 'School staff member',
                   calling_score='8', recommend_score='9',
                   presenter_engaged='Agree', presenter_knew_subject='Agree', presenter_organized='Agree',
                   valuable_comment='Understanding 988 and resources ' + PRIVATE if i % 2 else 'Recognizing crisis warning signs ' + PRIVATE,
                   improve_comment='More practice scenarios ' + PRIVATE if i % 2 else 'More time for discussion ' + PRIVATE)
        for skill in ('identify_crises', 'describe_988', 'know_when_to_use_988'):
            row[skill + '_before'] = 'Disagree' if i % 2 else 'Agree'
            row[skill + '_after'] = 'Agree' if i % 2 else 'Strongly agree'
        if flagged and i == 0:
            row['completion_time'] = '2026-10-19 10:00:10'
        if i == count - 1:
            row['county'] = PRIVATE
        rows.append([row.get(key) for key in keys])
    headers = [config.registry.questions[key].header for key in keys]
    if path.suffix == '.xlsx':
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Survey Data'
        sheet.append(headers)
        for row in rows: sheet.append(row)
        workbook.save(path)
        workbook.close()
    else:
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    return path


@pytest.mark.parametrize('suffix', ['.csv', '.xlsx'])
def test_export_to_bundle_and_pages(tmp_path, suffix):
    source = export(tmp_path / ('private' + suffix))
    original = source.read_bytes()
    bundle, audit = build_report(source, synthetic=True)
    assert bundle.data_kind == 'synthetic'
    assert bundle.input_hash == hashlib.sha256(original).hexdigest()
    assert source.read_bytes() == original
    headline = next(m for m in bundle.metrics if m.metric_id == 'agree_before' and m.dimensions == {'cohort': 'all_responses', 'skill': 'identify_crises'})
    assert (headline.value, headline.numerator, headline.denominator) == (.5, 40, 80)
    assert headline.ci is not None
    assert PRIVATE not in bundle.model_dump_json()
    assert PRIVATE in json.dumps(audit)  # Private audit is never shipped with Pages.
    assert bundle.findings and bundle.theme_data.questions
    assert audit['comment_review']['status'] == 'human_review_required'
    report = tmp_path / 'release.json'
    report.write_text(bundle.model_dump_json(), encoding='utf-8')
    site = tmp_path / 'site'
    prepare_pages(report, site)
    assert ReportBundle.model_validate_json((site / 'report.json').read_bytes()) == bundle
    assert ReportBundle.model_validate_json((site / 'report.synthetic.json').read_bytes()).data_kind == 'synthetic'
    assert (site / 'assets/forest-hero.mp4').stat().st_size == (ROOT / 'dashboard/assets/forest-hero.mp4').stat().st_size
    assert not (site / 'private-quality.json').exists()
    assert not (site / 'src').exists() and not (site / '.git').exists()
    with pytest.raises(ValueError): prepare_pages(report, site)


def test_cli_report_and_validation(tmp_path):
    source = export(tmp_path / 'input.csv')
    output, audit = tmp_path / 'report.json', tmp_path / 'private.json'
    result = CliRunner().invoke(app, ['report', str(source), '--output', str(output), '--audit-output', str(audit)])
    assert result.exit_code == 0, result.output
    assert ReportBundle.model_validate_json(output.read_bytes()).data_kind == 'survey'
    assert PRIVATE not in result.output
    assert CliRunner().invoke(app, ['validate-report', str(output)]).exit_code == 0
    assert CliRunner().invoke(app, ['validate-report', str(audit)]).exit_code == 1


def test_required_schema_failure_preserves_old_outputs(tmp_path):
    source = export(tmp_path / 'input.csv', missing=('describe_988_before',))
    output, audit = tmp_path / 'report.json', tmp_path / 'private.json'
    output.write_text('old report')
    audit.write_text('old audit')
    result = CliRunner().invoke(app, ['report', str(source), '--output', str(output), '--audit-output', str(audit)])
    assert result.exit_code == 1 and PRIVATE not in result.output
    assert output.read_text() == 'old report' and audit.read_text() == 'old audit'
    assert 'No demo was substituted' in result.output


def test_missing_optional_question_is_unavailable(tmp_path):
    source = export(tmp_path / 'input.csv', missing=('calling_score', 'valuable_comment'))
    bundle, _ = build_report(source)
    coverage = next(m for m in bundle.metrics if m.metric_id == 'calling_coverage')
    assert coverage.value is None and coverage.reason == 'question_missing_or_ambiguous'
    assert len(bundle.theme_data.questions) == 1
    assert any('optional questions' in note for note in bundle.quality_report.notes)


def test_nested_cohort_protection_does_not_hide_overall(tmp_path):
    bundle, _ = build_report(export(tmp_path / 'input.csv', flagged=True))
    overall = [m for m in bundle.metrics if m.metric_id == 'agree_after' and m.dimensions.get('cohort') == 'all_responses']
    clean = [m for m in bundle.metrics if m.metric_id == 'agree_after' and m.dimensions.get('cohort') == 'excluding_flagged']
    assert all(not m.suppressed and m.value == 1 for m in overall)
    assert all(m.suppressed for m in clean)
    flagged = next(m for m in bundle.metrics if m.metric_id == 'flagged_responses')
    assert flagged.suppressed and flagged.n is None
    for metric in bundle.metrics:
        if metric.suppressed:
            assert all(getattr(metric, field) is None for field in ('value', 'n', 'ci', 'numerator', 'denominator'))
            assert metric.provenance.parameters == {}
    for finding in bundle.findings:
        assert finding.metric_refs
        assert all(not next(m for m in bundle.metrics if m.key() == ref.key()).suppressed for ref in finding.metric_refs)


def test_public_allowlist_and_release_tampering(tmp_path):
    bundle, _ = build_report(export(tmp_path / 'input.csv'))
    assert all('training_date' not in m.dimensions and 'before_score' not in m.dimensions for m in bundle.metrics)
    assert all(m.metric_id != 'transition_count' for m in bundle.metrics)
    assert validate_release(bundle) == bundle
    invalid = bundle.model_copy(deep=True)
    invalid.metrics[0].dimensions['respondent_email'] = PRIVATE
    with pytest.raises(ValueError): validate_release(invalid)
    invalid = bundle.model_copy(deep=True)
    metric = next(m for m in invalid.metrics if m.metric_id == 'flagged_responses')
    metric.value = 1
    with pytest.raises(ValueError): validate_release(invalid)
    invalid = bundle.model_copy(deep=True)
    invalid.release_metadata = None
    with pytest.raises(ValueError): validate_release(invalid)


def test_repeated_analysis_has_stable_evidence(tmp_path):
    source = export(tmp_path / 'input.csv')
    one, _ = build_report(source)
    two, _ = build_report(source)
    assert one.metrics == two.metrics and one.findings == two.findings
    assert one.release_metadata == two.release_metadata


def test_small_survey_has_no_unsupported_findings(tmp_path):
    bundle, _ = build_report(export(tmp_path / 'input.csv', count=4))
    assert all(m.suppressed or m.value is None for m in bundle.metrics)
    assert not bundle.findings


def test_public_aggregate_matches_reference_workbook(survey_workbook):
    bundle, _ = build_report(survey_workbook)
    expected = {'identify_crises': (938, 1168), 'describe_988': (604, 1175), 'know_when_to_use_988': (723, 1199)}
    for skill, (before, after) in expected.items():
        entries = {m.metric_id: m for m in bundle.metrics if m.dimensions == {'cohort': 'all_responses', 'skill': skill}}
        assert (entries['agree_before'].numerator, entries['agree_after'].numerator) == (before, after)
        assert entries['agree_after'].n == 1299
        assert not entries['agree_before'].suppressed and not entries['agree_after'].suppressed
    answered = {q.question_id: next(m for m in bundle.metrics if m.key() == q.answered.key()).value for q in bundle.theme_data.questions}
    assert answered == {'valuable_comment': 1063, 'improve_comment': 651}


@pytest.mark.parametrize('suffix', ['.csv', '.xlsx'])
def test_private_comment_locators_survive_blank_records(tmp_path, suffix):
    source = export(tmp_path / ('input' + suffix))
    if suffix == '.xlsx':
        from openpyxl import load_workbook
        workbook = load_workbook(source)
        workbook.active.insert_rows(3)
        workbook.save(source)
        workbook.close()
    else:
        with source.open(newline='') as f: rows = list(csv.reader(f))
        rows.insert(2, [])
        with source.open('w', newline='') as f: csv.writer(f).writerows(rows)
    _, audit = build_report(source)
    records = audit['comment_review']['rows']
    assert [row['source_record'] for row in records[:2]] == [2, 4]
    assert audit['ingestion']['blank_row_count'] == 1
    assert audit['ingestion']['source_record_numbers'][-1] == 82


def test_new_responses_update_the_complete_report(tmp_path):
    source = export(tmp_path / 'input.csv')
    before, _ = build_report(source)
    with source.open(newline='') as f: rows = list(csv.reader(f))
    for index, original in enumerate(rows[1:21]):
        added = list(original)
        added[0] = f'new-response-{index}'
        rows.append(added)
    with source.open('w', newline='') as f: csv.writer(f).writerows(rows)
    after, _ = build_report(source)
    assert before.input_hash != after.input_hash
    assert before.metrics[0].provenance.config_hash == after.metrics[0].provenance.config_hash
    for bundle, expected in ((before, 80), (after, 100)):
        headline = next(m for m in bundle.metrics if m.metric_id == 'agree_after' and m.dimensions == {'skill': 'identify_crises', 'cohort': 'all_responses'})
        assert headline.n == expected and headline.value == 1
        assert not headline.suppressed
        validate_release(bundle)
