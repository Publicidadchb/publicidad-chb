"""Prepare an isolated environment, run tests and an isolated demonstration."""
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info < (3, 10):
        raise SystemExit('Se requiere Python 3.10 o posterior. En Windows puede usar py -3 scripts/setup.py.')
    environment = ROOT/'.venv'
    python = environment/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not environment.exists():
        # Runtime uses only the standard library: no package or credential download.
        venv.EnvBuilder(with_pip=False).create(environment)
    if not python.is_file():
        raise SystemExit('El entorno .venv existente está incompleto; se conserva sin sobrescribir. Revíselo con Codex.')
    subprocess.run([str(python), '-m', 'unittest', '-v', 'test_pipeline'], cwd=ROOT, check=True)
    demonstration = ROOT/'private'/'demo'/'demo.sqlite'
    if not demonstration.exists():
        subprocess.run([str(python), 'demo.py'], cwd=ROOT, check=True)
    subprocess.run([str(python), 'audit.py', '--db', str(demonstration), 'check'], cwd=ROOT, check=True)
    print('Preparación terminada. Sin dependencias externas. La base de demostración contiene datos ficticios.')
    print('El histórico real requiere recuperación local; consulte docs/CONTINUAR_EN_CODEX.md.')


if __name__ == '__main__':
    main()
