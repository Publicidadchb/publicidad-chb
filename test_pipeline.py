"""Portable migration tests. All fixtures are synthetic and isolated in temporary folders."""
import csv
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import audit
import demo


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chb-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder/'test.sqlite'
        self.c = audit.connect(self.db)
        self.addCleanup(self.c.close)

    def write_document(self, fixture):
        path = self.folder/'fixture.json'
        path.write_text(json.dumps(fixture), encoding='utf-8')
        return path

    def overview(self, members=None):
        path = self.folder/'synthetic.zip'
        members = members or {
            'Campañas(2026.01.01_2026.01.15).csv':
                'Nombre de la campaña,Clics,Coste\nCampaña ficticia,10,"2,50"\n',
            'Serie_temporal(2026.01.01_2026.01.15).csv':
                'Fecha,Clics\n15 ene 2026,10\n',
        }
        with zipfile.ZipFile(path, 'w') as archive:
            for name, text in members.items():
                archive.writestr(name, text.encode('utf-8-sig'))
        return path

    def test_overview_import_and_replay(self):
        args = (self.c, self.overview(), '2026-01-15T12:00:00-05:00',
                'synthetic-account', 'https://example.invalid/overview')
        with self.c:
            first = audit.import_overview(*args)
        before = audit.validate(self.c)
        with self.c:
            second = audit.import_overview(*args)
        self.assertFalse(first['replay'])
        self.assertTrue(second['replay'])
        self.assertEqual(first['raw_rows'], 2)
        self.assertEqual(before, audit.validate(self.c))
        self.assertEqual(before['tables']['raw_rows'], 2)

    def test_revisions_bounds_order_and_rollback(self):
        fixture = demo.document()
        source = self.write_document(fixture)
        with self.c:
            audit.import_ui(self.c, source)
        row = self.c.execute("SELECT * FROM v_latest_metrics WHERE metric_code='demo_query_count'").fetchone()
        self.assertEqual((row['qualifier'], row['value_decimal'], row['bound_decimal']), ('lt', None, '15'))
        for date, raw in [('2026-01-17T12:00:00-05:00', '20'), ('2026-01-14T12:00:00-05:00', '7')]:
            fixture['extracted_at'] = date
            fixture['records'][0]['metrics'][2]['raw'] = raw
            with self.c:
                audit.import_ui(self.c, self.write_document(fixture))
        row = self.c.execute("SELECT * FROM v_latest_metrics WHERE metric_code='demo_query_count'").fetchone()
        self.assertEqual(row['value_decimal'], '20')
        count = self.c.execute("SELECT count(*) FROM revisions r JOIN observations o ON o.id=r.observation_id WHERE metric_code='demo_query_count'").fetchone()[0]
        self.assertEqual(count, 3)
        before = audit.validate(self.c)
        fixture['extracted_at'] = '2026-01-18T12:00:00-05:00'
        fixture['records'][0]['metrics'][2]['raw'] = 'not a number'
        with self.assertRaises(ValueError):
            with self.c:
                audit.import_ui(self.c, self.write_document(fixture))
        self.assertEqual(before, audit.validate(self.c))

    def test_integrity_readonly_and_evidence(self):
        with self.c:
            audit.import_ui(self.c, self.write_document(demo.document()))
        report = audit.validate(self.c)
        self.assertEqual(report['integrity'], 'ok')
        self.assertEqual(report['foreign_key_errors'], [])
        self.assertEqual(report['revisions_without_evidence'], 0)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_evidence').fetchone()[0], 3)
        ro = audit.connect(self.db, readonly=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute('DELETE FROM raw_rows')
        finally:
            ro.close()

    def test_locales_and_semantics(self):
        self.assertEqual(audit.number('12,34 US$', 'USD'), ('12.34', 'exact', None, 12340000))
        self.assertEqual(audit.number('0,00', 'count')[0], '0.00')
        self.assertEqual(audit.number('4.5', 'stars_0_to_5')[0], '4.5')
        self.assertEqual(audit.number('1,25', 'attributed_count')[0], '1.25')
        for raw, unit in [('1,5', 'count'), ('1.23', 'USD'), ('-1', 'count')]:
            with self.assertRaises(ValueError):
                audit.number(raw, unit)

    def test_alternative_breakdowns_stay_separate(self):
        path = self.overview({
            'Día_y_hora(Día_2026.01.01_2026.01.15).csv': 'Día,Clics\nLunes,3\n',
            'Día_y_hora(Hora_2026.01.01_2026.01.15).csv': 'Hora,Clics\n10,3\n',
        })
        with self.c:
            audit.import_overview(self.c, path, '2026-01-15T12:00:00-05:00',
                                  'synthetic-account', 'https://example.invalid/overview')
        reports = {r[0] for r in self.c.execute('SELECT report_code FROM observations')}
        self.assertEqual(reports, {'Día_y_hora:Día', 'Día_y_hora:Hora'})

    def test_campaign_csv_and_period_validation(self):
        path = self.folder/'campaigns.csv'
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerows([
            ['Informe de campañas'], ['1 de enero de 2026 - 15 de enero de 2026'],
            ['Estado de la campaña', 'Campaña', 'Código de moneda', 'Presupuesto', 'Coste', 'Clics', 'Conversiones'],
            ['Habilitada', 'Campaña ficticia', 'USD', '1,00', '2,50', '10', '1,25'],
            ['Total: Cuenta', '', 'USD', '', '2,50', '10', '1,25'],
        ])
        path.write_text(buffer.getvalue(), encoding='utf-8-sig')
        args = (self.c, path, '2026-01-15T12:00:00-05:00', 'synthetic-account',
                'https://example.invalid/campaigns', '2026-01-01', '2026-01-15')
        with self.c:
            first = audit.import_campaigns(*args)
        self.assertEqual(first['campaigns'], 1)
        self.assertEqual(audit.validate(self.c)['tables']['raw_rows'], 2)
        with self.assertRaises(ValueError):
            with self.c:
                audit.import_campaigns(*args[:-1], '2026-01-16')

    def cli(self, *args):
        return subprocess.run([sys.executable, str(audit.BASE/'audit.py'), *map(str, args)],
                              capture_output=True, text=True)

    def test_cli_backup_and_query_guard(self):
        with self.c:
            audit.import_ui(self.c, self.write_document(demo.document()))
        before = self.db.read_bytes()
        result = self.cli('--db', self.db, 'query', '--sql', 'SELECT count(*) AS n FROM revisions')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [{'n': 3}])
        for sql in ['DELETE FROM revisions', "ATTACH DATABASE ':memory:' AS other", 'PRAGMA user_version=9']:
            self.assertNotEqual(self.cli('--db', self.db, 'query', '--sql', sql).returncode, 0)
        self.assertEqual(before, self.db.read_bytes())
        target = self.folder/'backup.sqlite'
        result = self.cli('--db', self.db, 'backup', target)
        self.assertEqual(result.returncode, 0, result.stderr)
        backup_before = target.read_bytes()
        self.assertNotEqual(self.cli('--db', self.db, 'backup', target).returncode, 0)
        self.assertEqual(backup_before, target.read_bytes())
        self.assertEqual(self.cli('--db', target, 'check').returncode, 0)

    def test_init_never_overwrites_and_missing_read_does_not_create(self):
        target = self.folder/'new.sqlite'
        self.assertNotEqual(self.cli('--db', target, 'check').returncode, 0)
        self.assertFalse(target.exists())
        result = self.cli('--db', target, 'init')
        self.assertEqual(result.returncode, 0, result.stderr)
        before = target.read_bytes()
        self.assertNotEqual(self.cli('--db', target, 'init').returncode, 0)
        self.assertEqual(before, target.read_bytes())

    def test_local_recovery_preserves_sources_and_existing_database(self):
        from scripts.restore_private import recover
        source = self.folder/'original'
        source.mkdir()
        database = source/'chavez_auditoria.sqlite'
        original = audit.connect(database)
        try:
            with original:
                audit.import_ui(original, self.write_document(demo.document()))
        finally:
            original.close()
        (source/'LEEME.txt').write_text('Original fixture', encoding='utf-8')
        original_bytes = database.read_bytes()
        private = self.folder/'private'
        first = recover(source, private)
        self.assertTrue(first['activated'])
        self.assertEqual(original_bytes, database.read_bytes())
        self.assertEqual((Path(first['snapshot'])/'LEEME.txt').read_text(), 'Original fixture')
        active_bytes = (private/database.name).read_bytes()
        second = recover(source, private)
        self.assertFalse(second['activated'])
        self.assertEqual(active_bytes, (private/database.name).read_bytes())
        self.assertNotEqual(first['snapshot'], second['snapshot'])

    def test_publication_guard_rejects_private_data(self):
        from scripts.check_public import inspect
        self.assertIn('private_artifact', inspect('private/database.sqlite', ''))
        self.assertIn('environment_file', inspect('.env', ''))
        fake_token = 'ghp_' + 'x'*30
        self.assertIn('github_token', inspect('config.txt', fake_token))
        self.assertEqual(inspect('demo.py', "account_key='synthetic'"), [])

    def test_meeting_preparation_rejects_demo_and_empty_database(self):
        from scripts.prepare_office import check_historical_database
        with self.assertRaisesRegex(ValueError, 'vacia'):
            check_historical_database(self.db)
        with self.c:
            audit.import_ui(self.c, self.write_document(demo.document()))
        with self.assertRaisesRegex(ValueError, 'cuentas de Google'):
            check_historical_database(self.db)

    def test_meeting_backup_preserves_source_and_does_not_claim_connection(self):
        from scripts.prepare_office import prepare_snapshot
        root = self.folder/'office'
        database = root/'private'/'chavez_auditoria.sqlite'
        fixture = demo.document()
        fixture['service'] = 'google_ads'
        connection = audit.connect(database)
        try:
            with connection:
                audit.import_ui(connection, self.write_document(fixture))
        finally:
            connection.close()
        before = database.read_bytes()
        first = prepare_snapshot(root)
        second = prepare_snapshot(root)
        self.assertFalse(first['remote_connection_confirmed'])
        self.assertEqual(first['validation']['tables']['runs'], 1)
        self.assertNotEqual(first['backup'], second['backup'])
        self.assertTrue(Path(first['backup']).is_file())
        self.assertEqual(before, database.read_bytes())


if __name__ == '__main__':
    unittest.main()
