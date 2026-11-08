"""Filter definitions, boundaries and independent mask reconciliation."""
import csv
import json
import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from everymind_insight.filters import FilterSpec, NumericRule, match_rule, selection
from everymind_insight.reporting import prepare_report
from test_reporting import export


@pytest.mark.parametrize(('operator','value','values','expected'), [
    ('below',30,None,[True,False,False,False,False,False]),
    ('above',3600,None,[False,False,False,False,True,False]),
    ('between',None,[30,3600],[False,True,True,True,False,False]),
    ('outside',None,[30,3600],[True,False,False,False,True,False]),
    ('equals',30,None,[False,True,False,False,False,False]),
    ('missing',None,None,[False,False,False,False,False,True]),
])
def test_numeric_operators(operator,value,values,expected):
    frame=pd.DataFrame({'duration_seconds':[29,30,31,3600,3601,np.nan]})
    rule=NumericRule(field='duration_seconds',operator=operator,value=value,values=values)
    assert match_rule(frame,rule).tolist()==expected


def test_dates_and_changes():
    frame=pd.DataFrame({'training_date':pd.to_datetime(['2026-10-01','2026-10-02',None]),
                        'know_when_to_use_988_before':pd.array([4,3,2],dtype='Int64'),
                        'know_when_to_use_988_after':pd.array([2,3,None],dtype='Int64')})
    assert match_rule(frame,NumericRule(field='training_date',operator='equals',value='2026-10-01')).tolist()==[True,False,False]
    assert match_rule(frame,NumericRule(field='know_when_to_use_988_change',operator='below',value=0)).tolist()==[True,False,False]


@pytest.mark.parametrize('payload', [
    {'schema_version':'2.0.0'}, {'exclusions':['made_up']}, {'speed_seconds':0}, {'rule_logic':'or'},
    {'speed_seconds':True}, {'long_seconds':False},
    {'numeric_rules':[{'field':'Id','operator':'equals','value':1}]},
    {'numeric_rules':[{'field':'duration_seconds','operator':'below','value':True}]},
    {'numeric_rules':[{'field':'duration_seconds','operator':'below','value':'thirty'}]},
    {'numeric_rules':[{'field':'duration_seconds','operator':'between','values':[40,30]}]},
    {'numeric_rules':[{'field':'duration_seconds','operator':'below','value':float('inf')}]},
    {'numeric_rules':[{'field':'training_date','operator':'equals','value':'2026-02-30'}]},
    {'numeric_rules':[{'field':'recommend_score','operator':'missing','value':0}]},
    {'numeric_rules':[{'field':'calling_score','operator':'below'}]},
])
def test_invalid_specs(payload):
    with pytest.raises(ValidationError): FilterSpec.model_validate(payload)


def test_each_checkbox_and_overlaps(tmp_path):
    prepared=prepare_report(export(tmp_path/'survey.csv'))
    f=prepared.quality.frame.copy()
    f['duration_seconds']=120.0
    f.loc[:19,'duration_seconds']=20
    f.loc[0,'duration_seconds']=0;f.loc[1,'duration_seconds']=-1
    f.loc[10:29,'is_straightliner']=True
    f.loc[30:39,'is_large_reversal']=True
    f.loc[40:49,'training_date']=pd.NaT
    f.loc[50:59,'is_invalid_timestamp']=True
    f.loc[60:69,'duration_seconds']=8000
    expected={'speeders':f.duration_seconds.lt(30),'long_duration':f.duration_seconds.gt(7200),
              'straightliners':f.is_straightliner,'large_drops':f.is_large_reversal,
              'invalid_training_date':f.training_date.isna(),'invalid_timestamps':f.is_invalid_timestamp | f.is_impossible_timestamp,
              'exact_duplicates':f['_response_group'].duplicated(keep='first')}
    for option,mask in expected.items():
        kept,_,_=selection(f,FilterSpec(exclusions=[option]))
        pd.testing.assert_series_equal(~kept,mask.astype(bool),check_names=False)
        assert int(kept.sum())+int((~kept).sum())==len(f)
    kept,options,_=selection(f,FilterSpec(exclusions=['speeders','straightliners']))
    assert int((~kept).sum())==30  # 20+20 minus 10 overlapping responses.
    for logic,removed in [('any',30),('all',10)]:
        spec=FilterSpec(rule_logic=logic,numeric_rules=[NumericRule(field='duration_seconds',operator='below',value=30),
                      NumericRule(field='recommend_score',operator='equals',value=9)])
        # Set the second numeric condition to rows 10..29.
        f['recommend_score']=0;f.loc[10:29,'recommend_score']=9
        kept,_,_=selection(f,spec)
        assert int((~kept).sum())==removed


def test_spec_hash_ignores_option_order():
    assert FilterSpec(exclusions=['speeders','straightliners']).spec_hash==FilterSpec(exclusions=['straightliners','speeders']).spec_hash


@pytest.mark.parametrize('invalid_first',[False,True])
def test_exact_duplicates_include_unknown_columns_and_keep_first_usable(tmp_path,invalid_first):
    path=export(tmp_path/'survey.csv')
    with path.open(encoding='utf-8',newline='') as source:
        reader=csv.reader(source);headers=next(reader);rows=list(reader)
    headers.append('New optional survey question')
    for i,row in enumerate(rows): row.append(f'different answer {i}')
    for i in [10,20]:
        response_id=rows[i][0];rows[i]=rows[0].copy();rows[i][0]=response_id
    if invalid_first: rows[0][0]=''
    with path.open('w',encoding='utf-8',newline='') as target:
        writer=csv.writer(target);writer.writerow(headers);writer.writerows(rows)
    frame=prepare_report(path).quality.frame.loc[lambda f:f.is_usable_id]
    kept,_,_=selection(frame,FilterSpec(exclusions=['exact_duplicates']))
    assert frame.index[~kept].tolist()==([20] if invalid_first else [10,20])
