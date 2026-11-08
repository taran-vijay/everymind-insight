"""Local API privacy boundary, input handling and report/export integration."""
import json

from fastapi.testclient import TestClient
import pytest

from everymind_insight.server import create_app
from everymind_insight.filters import FilterSpec
from test_filter_service import source_with_speeders
from test_reporting import export, PRIVATE


def client_for(source=None):
    return TestClient(create_app(source),base_url='http://127.0.0.1:8001')


def test_source_upload_in_memory_and_live_endpoints(tmp_path):
    source=source_with_speeders(tmp_path/'private.csv')
    original=source.read_bytes()
    with client_for() as client:
        assert not client.get('/api/fields').json()['available']
        assert client.post('/api/report',json={}).status_code==409
        result=client.post('/api/source?filename=private.csv',content=original,headers={'Content-Type':'application/octet-stream'})
        assert result.status_code==200,result.text
        fields=result.json(); assert fields['available'] and fields['total']==80
        headers={'X-Input-Hash':fields['input_hash']}
        payload=FilterSpec(exclusions=['speeders']).model_dump(mode='json')
        preview=client.post('/api/preview',json=payload,headers=headers)
        assert preview.status_code==200 and preview.json()['kept']==60
        response=client.post('/api/report',json=payload,headers=headers)
        assert response.status_code==200,response.text
        assert response.json()['filter_provenance']['removed_count']==20
        for path in ('/api/fields',): assert PRIVATE not in client.get(path).text
        assert PRIVATE not in preview.text+response.text
        assert source.read_bytes()==original
        for format in ('json','csv','parquet'):
            response=client.post('/api/export/'+format,json=payload,headers=headers)
            assert response.status_code==200,response.text
            assert response.headers['Cache-Control']=='no-store'
            assert 'attachment' in response.headers['Content-Disposition']


def test_invalid_upload_preserves_current_source_and_hash(tmp_path):
    with client_for(source_with_speeders(tmp_path/'survey.csv')) as client:
        original=client.get('/api/fields').json()['input_hash']
        assert client.post('/api/source?filename=survey.xlsx',content=b'not a workbook').status_code==422
        assert client.get('/api/fields').json()['input_hash']==original
        assert client.post('/api/report',json={},headers={'X-Input-Hash':'0'*64}).status_code==409


def test_privacy_rejections_and_invalid_specs(tmp_path):
    with client_for(source_with_speeders(tmp_path/'survey.csv',1)) as client:
        spec=FilterSpec(exclusions=['speeders']).model_dump(mode='json')
        preview=client.post('/api/preview',json=spec).json()
        assert preview['kept'] is None and preview['removed'] is None
        response=client.post('/api/report',json=spec)
        assert response.status_code==422 and 'fewer than 10' in response.text
        for payload in ({'schema_version':'9'}, {'numeric_rules':[{'field':'Id','operator':'equals','value':1}]}, {'numeric_rules':[{'field':'duration_seconds','operator':'between','values':[30,10]}]}):
            response=client.post('/api/preview',json=payload)
            assert response.status_code==422 and 'detail' in response.json()
            assert 'input' not in response.json()['detail'][0]


def test_server_only_serves_runtime_and_rejects_cross_site(tmp_path):
    with client_for(export(tmp_path/'survey.csv')) as client:
        for path in ('/','/app.js','/data-options.js','/styles.css','/report-data.js','/assets/inter-variable.ttf'):
            assert client.get(path).status_code==200
        for path in ('/reports/private-quality.json','/.git/config','/src/everymind_insight/cli.py','/assets/../../pyproject.toml','/report.json'):
            assert client.get(path).status_code==404
        assert client.get('/api/fields',headers={'Origin':'https://example.com'}).status_code==403
        assert client.post('/api/preview',json={},headers={'Origin':'null'}).status_code==403
        assert client.get('/api/fields',headers={'Host':'evil.example'}).status_code==400


def test_streamed_upload_is_bounded(tmp_path,monkeypatch):
    import everymind_insight.server as server
    monkeypatch.setattr(server,'MAX_UPLOAD',20)
    with client_for() as client:
        assert client.post('/api/source?filename=survey.csv',content=b'x'*21).status_code==413
        assert not client.get('/api/fields').json()['available']
