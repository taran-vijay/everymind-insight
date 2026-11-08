"""Beginner local workflow. Serve only an explicit dashboard package on loopback."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit
import webbrowser

from .cli import _write_json
from .pages import prepare_pages
from .reporting import build_report

ROOT = Path(__file__).resolve().parents[2]


class LocalHandler(SimpleHTTPRequestHandler):
    def allowed(self):
        path = unquote(urlsplit(self.path).path)
        if ".." in PurePosixPath(path).parts or "\\" in path:
            return False
        if path in {"/", "/index.html", "/app.js", "/styles.css", "/report-data.js", "/report.json", "/report.synthetic.json"}:
            return True
        if not path.startswith("/assets/"):
            return False
        target = Path(self.directory) / path.lstrip("/")
        return target.is_file() and not target.is_symlink() and target.suffix.lower() in {".mp4", ".jpg", ".png", ".ttf", ".woff", ".woff2", ".txt", ".md"}

    def do_GET(self):
        if self.allowed(): super().do_GET()
        else: self.send_error(404)

    def do_HEAD(self):
        if self.allowed(): super().do_HEAD()
        else: self.send_error(404)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, *args):
        pass


def pick_survey():
    try:
        import tkinter as tk
        from tkinter.filedialog import askopenfilename
        window = tk.Tk()
        window.withdraw()
        try:
            return askopenfilename(title="Select your private survey export", filetypes=[("Survey exports", "*.xlsx *.csv")])
        finally:
            window.destroy()
    except Exception:
        return input("File picker unavailable. Paste the survey file's full path: ").strip().strip('"').strip("'")


def run():
    print("\nEveryMind Insight — local survey workspace\n1. Explore the SYNTHETIC demo\n2. Analyze your private survey export\nQ. Quit")
    choice = input("Choose 1, 2 or Q: ").strip().lower()
    if choice == "q": return
    if choice not in {"1", "2"}:
        print("No mode selected. Reopen the launcher and choose 1 or 2.")
        return
    selected = ROOT / "fixtures/report.sample.json"
    if choice == "2":
        source = pick_survey()
        if not source:
            print("Canceled. No report was changed.")
            return
        sheet = input("Worksheet name [Enter for Survey Data; ignored for CSV]: ").strip() or None
        print("Analyzing the selected export locally…")
        bundle, audit = build_report(Path(source), sheet=sheet)
        selected = ROOT / "reports/report.json"
        _write_json(ROOT / "reports/private-quality.json", audit)
        _write_json(selected, bundle.model_dump(mode="json"))
        print("Saved reports/report.json and reports/private-quality.json. Keep the audit private. Topics and recommendations require staff review.")
    with TemporaryDirectory(prefix="everymind-") as directory:
        prepare_pages(selected, Path(directory), root=ROOT)
        handler = partial(LocalHandler, directory=directory)
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"Open {url}\nKeep this window open. Press Ctrl+C to stop.")
            webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nDashboard stopped.")


if __name__ == "__main__":
    try:
        run()
    except (OSError, ValueError, EOFError):
        print("Could not complete this run. Check the file, worksheet, ID and paired-question headers, output permissions and local-server access. No demo was substituted. Saved files may be from an earlier run; check their timestamps. Use the private check command for diagnostics.")
        raise SystemExit(1) from None
