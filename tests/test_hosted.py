from fastapi.testclient import TestClient
import pytest

from everymind_insight.server import create_app
from everymind_insight.hosted import Sessions, TTL
from test_reporting import export


def test_external_links_open_dashboard_without_exposing_survey_api(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'demo.onrender.com')
    navigation = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}
    with TestClient(create_app(hosted=True), base_url='https://demo.onrender.com') as client:
        for path in ('/', '/index.html'):
            response = client.get(path, headers=navigation)
            assert response.status_code == 200 and 'Training Insights' in response.text
            assert not client.cookies
        for path in ('/api/fields', '/api/source', '/report.synthetic.json', '/app.js'):
            assert client.get(path, headers=navigation).status_code == 403
        assert client.post('/', headers=navigation).status_code == 403
        assert client.post('/api/source?filename=survey.csv', content=b'fake', headers=navigation).status_code == 403
        assert client.delete('/api/source', headers=navigation).status_code == 403
        assert client.get('/', headers={**navigation, 'Sec-Fetch-Dest': 'iframe'}).status_code == 403
        assert client.get('/', headers={**navigation, 'Sec-Fetch-Mode': 'cors'}).status_code == 403
        assert client.get('/', headers={**navigation, 'Origin': 'https://evil.example'}).status_code == 403
    with TestClient(create_app(hosted=False), base_url='http://127.0.0.1') as client:
        assert client.get('/', headers=navigation).status_code == 403


def test_browser_uploads_are_isolated_and_clearable(tmp_path, monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'demo.onrender.com')
    app = create_app(hosted=True)
    with TestClient(app, base_url='https://demo.onrender.com') as one, TestClient(app, base_url='https://demo.onrender.com') as two:
        assert one.get('/health').status_code == 200
        page = one.get('/').text
        assert 'processed on this server' in page
        assert 'data-hosted="true"' in page
        assert 'Excel/CSV uploads are processed temporarily on this server.' in page
        assert 'Report files stay in your browser.' not in page
        assert one.post('/api/source?filename=survey.csv', content=export(tmp_path/'survey.csv').read_bytes()).status_code == 200
        assert one.get('/api/fields').json()['available']
        assert not two.get('/api/fields').json()['available']
        assert two.post('/api/report', json={}).status_code == 409
        assert one.get('/api/fields', headers={'Origin':'https://evil.example'}).status_code == 403
        assert one.get('/api/fields', headers={'Host':'evil.example'}).status_code == 400
        assert one.delete('/api/source').json()['cleared']
        assert not one.get('/api/fields').json()['available']
        assert not one.cookies


def test_session_capacity_signatures_and_expiry(monkeypatch):
    import everymind_insight.hosted as hosted
    store = Sessions()
    session, token = store.acquire(None)
    assert store.acquire(token)[0] is session
    assert store.acquire(token + 'tamper')[0] is not session
    store.acquire(None)
    store.acquire(None)
    assert store.acquire(None) == (None, None)
    future = session.touched + TTL + 1
    monkeypatch.setattr(hosted.time, 'monotonic', lambda: future)
    new, _ = store.acquire(token)
    assert new is not session and new.service is None


def test_page_visitors_do_not_consume_upload_capacity(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'demo.onrender.com')
    app = create_app(hosted=True)
    for _ in range(8):
        with TestClient(app, base_url='https://demo.onrender.com') as client:
            assert client.get('/api/fields').status_code == 200
            assert not client.cookies


def test_hosted_mode_requires_explicit_hostname(monkeypatch):
    monkeypatch.delenv('RENDER_EXTERNAL_HOSTNAME', raising=False)
    with pytest.raises(ValueError): create_app(hosted=True)
