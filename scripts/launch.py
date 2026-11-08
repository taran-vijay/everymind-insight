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
            'import everymind_insight.reporting; from pathlib import Path; '
            f'assert Path(everymind_insight.reporting.__file__).resolve().is_relative_to(Path({str(ROOT)!r}).resolve())'],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode:
            print('This environment is incomplete or points to a different checkout. Close the launcher, remove only .venv, and reopen it.')
            return 1
        return subprocess.call([str(python), '-m', 'everymind_insight.local_app'], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError):
        print('Setup failed. Check Python 3.11, your internet connection and folder permissions. To repair an incomplete setup, close this window, remove only .venv, and reopen the launcher.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
