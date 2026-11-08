from urllib.request import urlopen

from everymind_insight import judge_app


def test_launcher_opens_browser_only_after_upload_server_is_ready(monkeypatch):
    servers = []
    real_server = judge_app.uvicorn.Server
    def factory(config):
        server = real_server(config)
        servers.append(server)
        return server
    monkeypatch.setattr(judge_app.uvicorn, 'Server', factory)
    observed = []
    def open_browser(address):
        try:
            with urlopen(address + 'api/fields', timeout=5) as response:
                observed.append((address, response.status))
                response.read()
        finally:
            servers[0].should_exit = True
    monkeypatch.setattr(judge_app.webbrowser, 'open', open_browser)
    judge_app.run()
    assert len(observed) == 1 and observed[0][1] == 200
    assert observed[0][0].startswith('http://127.0.0.1:')
