"""Prepare the office project and a private backup; remote pairing is a separate approval."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import audit
from scripts.restore_private import snapshot_database


def check_historical_database(database):
    if not database.is_file():
        raise ValueError('Falta la base historica original. No se considera recuperada la demostracion.')
    connection = audit.connect(database, readonly=True)
    try:
        report = audit.validate(connection)
        services = {row[0] for row in connection.execute('SELECT service FROM accounts')}
    finally:
        connection.close()
    if report['integrity'] != 'ok' or report['foreign_key_errors'] or report['revisions_without_evidence']:
        raise ValueError('La base no supera la comprobacion de integridad; se conserva sin cambios.')
    if not report['tables']['runs'] or not report['tables']['raw_rows']:
        raise ValueError('La base esta vacia; falta recuperar el historico original.')
    if not services.intersection({'google_ads', 'google_business_profile', 'gbp'}):
        raise ValueError('La base no contiene cuentas de Google reconocidas. No usar la demostracion como historico.')
    return report


def prepare_snapshot(root):
    root = Path(root)
    database = root/'private'/'chavez_auditoria.sqlite'
    report = check_historical_database(database)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = root/'private'/'backups'/f'antes_reunion_{stamp}.sqlite'
    backup.parent.mkdir(parents=True, exist_ok=True)
    snapshot_database(database, backup)
    check_historical_database(backup)
    record = {
        'prepared_at_utc': stamp,
        'project_root': str(root.resolve()),
        'database': str(database.resolve()),
        'backup': str(backup.resolve()),
        'validation': report,
        'remote_connection_confirmed': False,
        'meeting_status': 'base_preparada_emparejamiento_pendiente',
    }
    folder = root/'private'/'reunion'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/f'preparacion_{stamp}.json').open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Directorio original si no se localiza automaticamente')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.exit(1, 'Se requiere Python 3.10 o posterior.\n')
    subprocess.run([sys.executable, 'scripts/setup.py'], cwd=ROOT, check=True)
    python = ROOT/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if args.source or not (ROOT/'private'/'chavez_auditoria.sqlite').exists():
        command = [str(python), 'scripts/restore_private.py']
        if args.source:
            command += ['--source', str(args.source.resolve())]
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            parser.exit(result.returncode, 'Recuperacion pendiente. Los originales no se han sustituido.\n')
    try:
        record = prepare_snapshot(ROOT)
    except (ValueError, OSError, audit.sqlite3.Error) as error:
        parser.exit(1, str(error)+'\n')
    print(json.dumps(record, ensure_ascii=False, indent=2))
    print('Base y respaldo preparados. La conexion casa-oficina aun requiere emparejamiento y comprobacion.')
    print('Seguir docs/REUNION_CASA_OFICINA.md. Este programa no habilita acceso remoto ni sube datos.')


if __name__ == '__main__':
    main()
