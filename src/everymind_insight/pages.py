"""Build an explicit static-site allowlist, never a copy of the repository."""

import shutil
from pathlib import Path

from .release import validate_release
from .schemas import ReportBundle

ROOT = Path(__file__).resolve().parents[2]


def copy_runtime(destination: Path, *, root: Path = ROOT):
    for name in ("index.html", "app.js", "report-data.js", "styles.css"):
        source = root / "dashboard" / name
        if source.is_symlink(): raise ValueError("Runtime sources must be ordinary files.")
        shutil.copy2(source, destination / name)
    source = root / "dashboard/assets"
    for file in source.rglob("*"):
        if file.is_symlink(): raise ValueError("Assets must not contain symbolic links.")
        if file.is_file():
            # Preserve the existing media/fonts/licenses without optimization.
            if file.suffix.lower() not in {".mp4", ".jpg", ".png", ".ttf", ".woff", ".woff2", ".txt", ".md"}:
                raise ValueError("Unexpected runtime asset.")
            target = destination / "assets" / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)


def prepare_pages(report: Path, out: Path, *, root: Path = ROOT):
    bundle = validate_release(ReportBundle.model_validate_json(report.read_bytes()))
    sample = ReportBundle.model_validate_json((root / "fixtures/report.sample.json").read_bytes())
    if sample.data_kind != "synthetic": raise ValueError("The demo must be synthetic.")
    # Never delete/reuse an arbitrary folder that might hold a survey or audit.
    if out.is_symlink() or (out.exists() and any(out.iterdir())):
        raise ValueError("Choose a new or empty output directory.")
    out.mkdir(parents=True, exist_ok=True)
    copy_runtime(out, root=root)
    (out / "report.json").write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (out / "report.synthetic.json").write_text(sample.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (out / ".nojekyll").touch()
