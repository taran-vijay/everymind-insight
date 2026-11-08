"""Start the actual upload server and open it after startup; no menu required."""
import socket
import threading
import webbrowser

import uvicorn

from .server import create_app


def run(*, open_browser=True):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        address = f'http://127.0.0.1:{listener.getsockname()[1]}/'
        server = uvicorn.Server(uvicorn.Config(create_app(), host='127.0.0.1', log_level='warning', access_log=False))
        stop = threading.Event()

        def announce():
            while not stop.wait(.1):
                if server.started:
                    print(f'\nEveryMind is ready: {address}\nSelect your XLSX or CSV in the page. Keep this window open; press Ctrl+C to stop.\n', flush=True)
                    if open_browser:
                        try: webbrowser.open(address)
                        except webbrowser.Error: pass
                    return

        watcher = threading.Thread(target=announce, daemon=True)
        watcher.start()
        try:
            server.run(sockets=[listener])
        finally:
            stop.set()
            watcher.join(timeout=1)


if __name__ == '__main__':
    try: run()
    except KeyboardInterrupt: pass
    except OSError:
        print('Could not start the local server. Check local network permissions and rerun the command. Nothing was published.')
        raise SystemExit(1) from None
