import csv
import io
import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from everymind_insight.cli import app
from everymind_insight.filter_service import FilterService, export_report, histogram
from everymind_insight.filters import FilterSpec, NumericRule
from everymind_insight.release import validate_release
from everymind_insight.reporting import build_report
from test_reporting import export, PRIVATE


def source_with_speeders(path,count=20):
    export(path)
    with path.open(encoding='utf-8',newline='') as f: reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
    for i,row in enumerate(rows): row['Completion time']='2026-10-19 10:00:10' if i<count else '2026-10-19 10:02:00'
    with path.open('w',encoding='utf-8',newline='') as f: writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)
    return path


def test_default_matches_pipeline_and_reference_counts(tmp_path,survey_workbook):
    source=survey_workbook
    current=FilterService(source)
    actual=current.report(FilterSpec())
    baseline,_=build_report(source)
    assert actual.metrics==baseline.metrics
    expected={'identify_crises':(938,1168),'describe_988':(604,1175),'know_when_to_use_988':(723,1199)}
    for skill,(before,after) in expected.items():
        for identifier,value in [('agree_before',before),('agree_after',after)]:
            m=next(m for m in actual.metrics if m.metric_id==identifier and m.dimensions=={'skill':skill,'cohort':'all_responses'})
            assert (m.numerator,m.denominator)==(value,1299)


def test_preview_recompute_cache_and_exports(tmp_path):
    service=FilterService(source_with_speeders(tmp_path/'private.csv'))
    spec=FilterSpec(exclusions=['speeders'])
    preview=service.preview(spec)
    assert (preview['kept'],preview['removed'],preview['total'])==(60,20,80)
    assert preview['option_counts']['speeders']==20
    assert preview['headlines']
    first=service.open_report(spec)
    assert first.model_dump_json()==service.open_report(spec).model_dump_json()
    assert first.filter_provenance.spec_hash==spec.spec_hash
    assert first.filter_provenance.included_count==60
    validate_release(first)
    assert PRIVATE not in first.model_dump_json()
    for format in ('json','csv','parquet'):
        data=export_report(first,format)
        if format=='parquet':
            table=pd.read_parquet(io.BytesIO(data)); assert table.included_count.eq(60).all();assert table.filter_banner.str.startswith('Filtered view:').all()
        else: assert b'Filtered view:' in data and PRIVATE.encode() not in data
    assert not any('raw' in c or c in {'id','valuable_comment'} for c in table.columns)


def test_requested_numeric_examples_match_real_rows(survey_workbook):
    service=FilterService(survey_workbook)
    f=service.frame
    cases=[
        (FilterSpec(numeric_rules=[NumericRule(field='duration_seconds',operator='below',value=30),
                                  NumericRule(field='duration_seconds',operator='above',value=3600)]),
         f.duration_seconds.lt(30) | f.duration_seconds.gt(3600)),
        (FilterSpec(numeric_rules=[NumericRule(field='know_when_to_use_988_change',operator='below',value=0)]),
         f.know_when_to_use_988_after.lt(f.know_when_to_use_988_before))
    ]
    for spec,removed in cases:
        preview=service.preview(spec)
        assert preview['can_apply'] and preview['removed']==int(removed.sum())
        report=service.report(spec)
        assert report.filter_provenance.removed_count==int(removed.sum())
        assert report.filter_provenance.included_count==int((~removed).sum())
        reverse=spec.model_copy(update={'numeric_rules':list(reversed(spec.numeric_rules))})
        assert report.model_dump_json()==service.report(reverse).model_dump_json()
        validate_release(report)


@pytest.mark.parametrize('count',[1,9])
def test_small_removed_complements_are_not_revealed(tmp_path,count):
    service=FilterService(source_with_speeders(tmp_path/'private.csv',count))
    spec=FilterSpec(exclusions=['speeders'])
    preview=service.preview(spec)
    assert not preview['can_apply'] and preview['kept'] is None and preview['removed'] is None
    assert preview['removed_label']=='fewer than 10' and preview['headlines']==[]
    with pytest.raises(ValueError,match='fewer than 10'):service.report(spec)


def test_small_kept_and_neighbor_view_rejected(tmp_path):
    service=FilterService(source_with_speeders(tmp_path/'private.csv'))
    with pytest.raises(ValueError,match='fewer than 10'):
        service.report(FilterSpec(numeric_rules=[NumericRule(field='duration_seconds',operator='above',value=0)]))
    base=service.open_report(FilterSpec(exclusions=['speeders']))
    # Changing one additional response must not be exposed by comparing views.
    service.released.append(pd.Series([i>=21 for i in range(80)],index=service.frame.index))
    with pytest.raises(ValueError,match='already opened'):service.report(FilterSpec(exclusions=['speeders']))


def test_fields_are_aggregate_and_bins_merge_small_counts(tmp_path):
    service=FilterService(source_with_speeders(tmp_path/'private.csv'))
    data=service.fields()
    assert PRIVATE not in json.dumps(data)
    assert len(data['fields'])==16
    for field in data['fields']:
        assert all(b['count']>=10 for b in field['histogram'])
    bins=histogram(pd.Series([0]*50+[10]*49+[10000]))
    assert sum(b['count'] for b in bins)==100
    assert all(b['count']>=10 for b in bins)
    service.frame.loc[service.frame.index[0],'recommend_score']=pd.NA
    field=next(f for f in service.fields()['fields'] if f['id']=='recommend_score')
    assert field['missing'] is None and field['histogram']==[]
    assert field['min'] is not None


def test_cli_filtered_report_is_reproducible(tmp_path):
    source=source_with_speeders(tmp_path/'private.csv')
    spec=tmp_path/'filters.json';spec.write_text(FilterSpec(exclusions=['speeders']).model_dump_json(),encoding='utf-8')
    output=tmp_path/'report.json';audit=tmp_path/'audit.json';csv_file=tmp_path/'report.csv';parquet=tmp_path/'report.parquet'
    result=CliRunner().invoke(app,['report',str(source),'--filters',str(spec),'--output',str(output),'--audit-output',str(audit),'--csv-output',str(csv_file),'--parquet-output',str(parquet)])
    assert result.exit_code==0,result.output
    bundle=json.loads(output.read_text(encoding='utf-8'))
    assert bundle['filter_provenance']['included_count']==60
    assert PRIVATE not in output.read_text(encoding='utf-8')


def test_cli_invalid_spec_explains_boundary_error(tmp_path):
    source=source_with_speeders(tmp_path/'private.csv')
    spec=tmp_path/'filters.json'
    spec.write_text(json.dumps({'numeric_rules':[{'field':'duration_seconds','operator':'between','values':[3600,30]}]}),encoding='utf-8')
    result=CliRunner().invoke(app,['report',str(source),'--filters',str(spec)])
    assert result.exit_code != 0
    assert 'lower boundary must not exceed' in result.output
    assert PRIVATE not in result.output
