"""Create an isolated demonstration; all metrics and account identifiers are fictional."""
import argparse
import json
from pathlib import Path

import audit


def document():
    return {
        'service': 'demo', 'account_key': 'demo-no-real-account',
        'key_type': 'synthetic', 'name': 'DEMO - DATOS FICTICIOS',
        'url': 'https://example.invalid/demo',
        'extracted_at': '2026-01-15T12:00:00-05:00',
        'records': [{'kind': 'location', 'metrics': [
            {'code': 'demo_clicks', 'raw': '10', 'start': '2026-01-01', 'end': '2026-01-15'},
            {'code': 'demo_cost', 'raw': '2,50', 'unit': 'USD', 'start': '2026-01-01', 'end': '2026-01-15'},
            {'code': 'demo_query_count', 'raw': '<15', 'start': '2026-01-01', 'end': '2026-01-15'},
        ]}],
        'coverage': [['Demostración', 'limited', 'Datos ficticios. No representan resultados de CHB.']],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=audit.BASE/'private'/'demo'/'demo.sqlite')
    args = parser.parse_args()
    if args.db.exists():
        parser.error('La demostración ya existe; elija otro destino para conservarla')
    args.db.parent.mkdir(parents=True, exist_ok=True)
    source = args.db.with_suffix('.synthetic.json')
    with source.open('x', encoding='utf-8') as stream:
        json.dump(document(), stream, ensure_ascii=False, indent=2)
    connection = audit.connect(args.db)
    try:
        with connection:
            audit.import_ui(connection, source)
        print(json.dumps({'demo': True, **audit.validate(connection)}, ensure_ascii=False, indent=2))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
