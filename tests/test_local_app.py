import json
import threading
import shutil
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from everymind_insight import local_app
from everymind_insight.local_app import LocalHandler
from everymind_insight.pages import prepare_pages
from everymind_insight.schemas import ReportBundle
from test_reporting import ROOT, PRIVATE, export


def test_live_server_rejects_audits_and_traversal(tmp_path):
    prepare_pages(ROOT / 'fixtures/report.sample.json', tmp_path / 'site')
    (tmp_path / 'site/private-quality.json').write_text(PRIVATE)
    (tmp_path / 'survey.csv').write_text(PRIVATE)
    with ThreadingHTTPServer(('127.0.0.1', 0), partial(LocalHandler, directory=str(tmp_path / 'site'))) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for route in ('/', '/report.json', '/report.synthetic.json', '/assets/inter-variable.ttf'):
                with urlopen(base + route) as response:
                    assert response.status == 200 and response.headers['Cache-Control'] == 'no-store'
                    response.read()
            for route in ('/private-quality.json', '/../survey.csv', '/%2e%2e/survey.csv', '/assets/../private-quality.json', '/.git/config', '/src/everymind_insight/cli.py'):
                with pytest.raises(HTTPError) as error: urlopen(base + route)
                assert error.value.code == 404
        finally:
            server.shutdown()
            thread.join()


def test_cancel_does_not_replace_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(local_app, 'ROOT', tmp_path)
    monkeypatch.setattr('builtins.input', lambda _: '2')
    monkeypatch.setattr(local_app, 'pick_survey', lambda: '')
    local_app.run()
    assert not (tmp_path / 'reports').exists()


def test_survey_launcher_saves_separate_outputs(tmp_path, monkeypatch):
    source = export(tmp_path / 'private export.xlsx')
    root = tmp_path / 'project with spaces'
    root.mkdir()
    # Use original runtime assets without copying the source workbook into site.
    shutil.copytree(ROOT / 'dashboard', root / 'dashboard', ignore=shutil.ignore_patterns('report.json'))
    shutil.copytree(ROOT / 'fixtures', root / 'fixtures')
    monkeypatch.setattr(local_app, 'ROOT', root)
    answers = iter(['2', ''])
    monkeypatch.setattr('builtins.input', lambda _: next(answers))
    monkeypatch.setattr(local_app, 'pick_survey', lambda: str(source))
    opened = []
    monkeypatch.setattr(local_app.webbrowser, 'open', opened.append)
    monkeypatch.setattr(local_app.ThreadingHTTPServer, 'serve_forever', lambda self: (_ for _ in ()).throw(KeyboardInterrupt))
    local_app.run()
    bundle = ReportBundle.model_validate_json((root / 'reports/report.json').read_bytes())
    assert bundle.data_kind == 'survey'
    assert PRIVATE not in bundle.model_dump_json()
    assert json.loads((root / 'reports/private-quality.json').read_text())['visibility'] == 'private_local_diagnostics'
    assert opened[0].startswith('http://127.0.0.1:')


def test_demo_leaves_a_saved_survey_report_unchanged(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    shutil.copytree(ROOT / 'dashboard', root / 'dashboard', ignore=shutil.ignore_patterns('report.json'))
    shutil.copytree(ROOT / 'fixtures', root / 'fixtures')
    (root / 'reports').mkdir()
    saved = root / 'reports/report.json'
    saved.write_text('old survey report')
    monkeypatch.setattr(local_app, 'ROOT', root)
    monkeypatch.setattr('builtins.input', lambda _: '1')
    monkeypatch.setattr(local_app.webbrowser, 'open', lambda _: None)
    monkeypatch.setattr(local_app.ThreadingHTTPServer, 'serve_forever', lambda self: (_ for _ in ()).throw(KeyboardInterrupt))
    local_app.run()
    assert saved.read_text() == 'old survey report'
