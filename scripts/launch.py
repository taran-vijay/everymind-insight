"""First-run setup for the supported local checkout, using the standard library."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info[:2] != (3, 11):
        print('Install Python 3.11 from https://www.python.org/downloads/ and reopen the launcher.')
        return 1
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    try:
        if not python.exists():
            print('Preparing your local environment. Internet is needed for installing tools; survey data is not uploaded.')
            # Resolve interpreter launchers so managed Python installations can
            # find their standard library inside the new environment.
            interpreter = Path(getattr(sys, '_base_executable', sys.executable)).resolve()
            subprocess.run([str(interpreter), '-m', 'venv', str(environment)], check=True)
            subprocess.run([str(python), '-m', 'pip', 'install', '-e', str(ROOT) + '[test]'], cwd=ROOT, check=True)
        check = subprocess.run([str(python), '-c',
            'import everymind_insight.reporting, everymind_insight.server, uvicorn; from pathlib import Path; '
            f'assert Path(everymind_insight.reporting.__file__).resolve().is_relative_to(Path({str(ROOT)!r}).resolve())'],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode:
            print('Updating the local environment for this checkout…')
            subprocess.run([str(python), '-m', 'pip', 'install', '-e', str(ROOT) + '[test]'], cwd=ROOT, check=True)
        module = 'everymind_insight.judge_app' if '--judge' in sys.argv else 'everymind_insight.local_app'
        return subprocess.call([str(python), '-m', module], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError):
        print('Setup failed. Check Python 3.11, your internet connection and folder permissions. To repair an incomplete setup, close this window, remove only .venv, and reopen the launcher.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
