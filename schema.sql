PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS businesses(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL REFERENCES businesses, service TEXT NOT NULL, source_key TEXT NOT NULL, key_type TEXT NOT NULL, timezone TEXT NOT NULL, currency TEXT, UNIQUE(service,source_key));
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts, extracted_at TEXT NOT NULL, imported_at TEXT NOT NULL, source_url TEXT NOT NULL, method TEXT NOT NULL, import_key TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS artifacts(id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL, media_type TEXT NOT NULL, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS run_artifacts(run_id INTEGER REFERENCES runs, artifact_id INTEGER REFERENCES artifacts, PRIMARY KEY(run_id,artifact_id));
CREATE TABLE IF NOT EXISTS raw_tables(id INTEGER PRIMARY KEY, artifact_id INTEGER NOT NULL REFERENCES artifacts, member_name TEXT NOT NULL, report_code TEXT NOT NULL, headers_json TEXT NOT NULL, UNIQUE(artifact_id,member_name));
CREATE TABLE IF NOT EXISTS raw_rows(id INTEGER PRIMARY KEY, table_id INTEGER NOT NULL REFERENCES raw_tables, row_number INTEGER NOT NULL CHECK(row_number>0), values_json TEXT NOT NULL, UNIQUE(table_id,row_number));
CREATE TABLE IF NOT EXISTS entities(id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts, kind TEXT NOT NULL, source_key TEXT NOT NULL, name TEXT NOT NULL, identity_basis TEXT NOT NULL CHECK(identity_basis IN ('native','provisional','account')), parent_id INTEGER REFERENCES entities, UNIQUE(account_id,kind,source_key));
CREATE TABLE IF NOT EXISTS entity_observations(id INTEGER PRIMARY KEY, entity_id INTEGER NOT NULL REFERENCES entities, run_id INTEGER NOT NULL REFERENCES runs, raw_row_id INTEGER REFERENCES raw_rows, attributes_json TEXT NOT NULL, UNIQUE(entity_id,run_id,raw_row_id));
CREATE TABLE IF NOT EXISTS periods(id INTEGER PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL, grain TEXT NOT NULL, UNIQUE(start_date,end_date,grain), CHECK(start_date<=end_date));
CREATE TABLE IF NOT EXISTS metric_definitions(code TEXT PRIMARY KEY, unit TEXT NOT NULL, aggregation TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY, entity_id INTEGER NOT NULL REFERENCES entities, report_code TEXT NOT NULL, period_id INTEGER NOT NULL REFERENCES periods, metric_code TEXT NOT NULL REFERENCES metric_definitions, dimensions_json TEXT NOT NULL, UNIQUE(entity_id,report_code,period_id,metric_code,dimensions_json));
CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY, observation_id INTEGER NOT NULL REFERENCES observations, run_id INTEGER NOT NULL REFERENCES runs, value_decimal TEXT, qualifier TEXT NOT NULL CHECK(qualifier IN ('exact','lt','missing')), bound_decimal TEXT, raw_value TEXT NOT NULL, money_micros INTEGER, UNIQUE(observation_id,run_id), CHECK((qualifier='exact' AND value_decimal IS NOT NULL) OR (qualifier='lt' AND value_decimal IS NULL AND bound_decimal IS NOT NULL) OR (qualifier='missing' AND value_decimal IS NULL)));
CREATE TABLE IF NOT EXISTS evidence(run_id INTEGER NOT NULL REFERENCES runs, revision_id INTEGER NOT NULL REFERENCES revisions, raw_row_id INTEGER NOT NULL REFERENCES raw_rows, PRIMARY KEY(run_id,revision_id,raw_row_id));
CREATE TABLE IF NOT EXISTS coverage(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs, section TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('reviewed','partial','pending','limited')), detail TEXT NOT NULL, UNIQUE(run_id,section));
CREATE TABLE IF NOT EXISTS findings(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs, finding_key TEXT NOT NULL, priority INTEGER NOT NULL CHECK(priority BETWEEN 0 AND 3), fact TEXT NOT NULL, interpretation TEXT NOT NULL, recommendation TEXT NOT NULL, evidence_json TEXT NOT NULL, UNIQUE(run_id,finding_key));
CREATE INDEX IF NOT EXISTS revision_history ON revisions(observation_id,id DESC);
CREATE INDEX IF NOT EXISTS entity_lookup ON entities(account_id,kind,name);
CREATE INDEX IF NOT EXISTS metric_lookup ON observations(report_code,period_id,metric_code);
CREATE VIEW IF NOT EXISTS v_latest_metrics AS
 SELECT o.id AS observation_id,e.name,e.kind,e.identity_basis,a.service,o.report_code,p.start_date,p.end_date,p.grain,CASE WHEN p.grain LIKE '%_to_date' OR p.end_date>substr(datetime(run.extracted_at,'-5 hours'),1,10) THEN 1 ELSE 0 END AS partial,o.metric_code,m.unit,o.dimensions_json,r.value_decimal,r.qualifier,r.bound_decimal,r.raw_value,r.money_micros,run.extracted_at,r.id AS revision_id
 FROM observations o JOIN revisions r ON r.observation_id=o.id JOIN entities e ON e.id=o.entity_id JOIN accounts a ON a.id=e.account_id JOIN periods p ON p.id=o.period_id JOIN metric_definitions m ON m.code=o.metric_code JOIN runs run ON run.id=r.run_id
 WHERE r.id=(SELECT r2.id FROM revisions r2 JOIN runs t2 ON t2.id=r2.run_id WHERE r2.observation_id=o.id ORDER BY t2.extracted_at DESC,r2.id DESC LIMIT 1);
CREATE VIEW IF NOT EXISTS v_evidence AS
 SELECT ev.run_id,ev.revision_id,ru.extracted_at,ru.source_url,art.sha256,t.member_name,rr.row_number,rr.values_json
 FROM evidence ev JOIN runs ru ON ru.id=ev.run_id JOIN raw_rows rr ON rr.id=ev.raw_row_id JOIN raw_tables t ON t.id=rr.table_id JOIN artifacts art ON art.id=t.artifact_id;
