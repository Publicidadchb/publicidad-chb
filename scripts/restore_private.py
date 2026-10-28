"""Recover the original local audit directory without uploading data or overwriting history."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import audit


def snapshot_database(source, destination):
    # Exclusive creation prevents replacing an existing file.
    with destination.open('xb'):
        pass
    original = audit.connect(source, readonly=True)
    target = sqlite3.connect(destination)
    try:
        original.backup(target)
    finally:
        target.close()
        original.close()


def recover(source, private):
    source, private = Path(source).resolve(), Path(private).resolve()
    database = source/'chavez_auditoria.sqlite'
    if not database.is_file():
        raise ValueError('No se encontró chavez_auditoria.sqlite en la carpeta indicada')
    if private.is_relative_to(source):
        raise ValueError('El destino privado debe estar fuera de la carpeta original')
    connection = audit.connect(database, readonly=True)
    try:
        report = audit.validate(connection)
    finally:
        connection.close()
    if report['integrity'] != 'ok' or report['foreign_key_errors'] or report['revisions_without_evidence']:
        raise ValueError('La base original no superó la comprobación de integridad; se conserva sin modificar')
    private.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix='recuperado-', dir=private))
    ignored = {database.name, *(database.name+suffix for suffix in ('-wal', '-shm', '-journal')),
               '.git', '.venv', '__pycache__'}
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=lambda _directory, names: ignored.intersection(names))
    snapshot_database(database, destination/database.name)
    current = private/database.name
    activated = False
    if not current.exists():
        snapshot_database(destination/database.name, current)
        activated = True
    result = {
        'recovered_at': datetime.now(timezone.utc).isoformat(),
        'source': str(source), 'snapshot': str(destination),
        'active_database': str(current), 'activated': activated,
        'existing_database_preserved': not activated,
        'validation': report,
    }
    with (destination/'recovery.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


def candidates():
    # This is the original Codex output layout; do not scan unrelated user files.
    base = Path.home()/'Documents'/'Codex'
    if not base.is_dir():
        return []
    return sorted({p.parent.resolve() for p in base.glob('*/*/outputs/auditoria_chavez/chavez_auditoria.sqlite')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Carpeta original auditoria_chavez')
    args = parser.parse_args()
    source = args.source
    if source is None:
        found = candidates()
        if not found:
            parser.exit(2, 'No se encontró el histórico original en este ordenador. No se ha creado una base histórica. Ejecute este recuperador en el equipo donde se hizo la auditoría o indique --source.\n')
        if len(found) > 1:
            parser.exit(2, 'Hay varias carpetas originales; indique --source para conservar la elección explícita.\n')
        source = found[0]
    try:
        result = recover(source, ROOT/'private')
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, str(error)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
