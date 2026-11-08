from fastapi.testclient import TestClient
import pytest

from everymind_insight.server import create_app
from everymind_insight.hosted import Sessions, TTL
from test_reporting import export


def test_browser_uploads_are_isolated_and_clearable(tmp_path, monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'demo.onrender.com')
    app = create_app(hosted=True)
    with TestClient(app, base_url='https://demo.onrender.com') as one, TestClient(app, base_url='https://demo.onrender.com') as two:
        assert one.get('/health').status_code == 200
        assert 'processed on this server' in one.get('/').text
        assert one.post('/api/source?filename=survey.csv', content=export(tmp_path/'survey.csv').read_bytes()).status_code == 200
        assert one.get('/api/fields').json()['available']
        assert not two.get('/api/fields').json()['available']
        assert two.post('/api/report', json={}).status_code == 409
        assert one.get('/api/fields', headers={'Origin':'https://evil.example'}).status_code == 403
        assert one.get('/api/fields', headers={'Host':'evil.example'}).status_code == 400
        assert one.delete('/api/source').json()['cleared']
        assert not one.get('/api/fields').json()['available']


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


def test_hosted_mode_requires_explicit_hostname(monkeypatch):
    monkeypatch.delenv('RENDER_EXTERNAL_HOSTNAME', raising=False)
    with pytest.raises(ValueError): create_app(hosted=True)
