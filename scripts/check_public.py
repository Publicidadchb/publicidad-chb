"""Check candidate Git files for private artifacts and common credential patterns."""
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_FOLDERS = {'private', 'raw', 'backups', 'outputs', 'work', '.ssh', '.aws', '.venv', 'node_modules'}
PRIVATE_SUFFIXES = {'.sqlite', '.sqlite3', '.db', '.pdf', '.zip', '.csv', '.xlsx', '.xls', '.pem', '.key', '.p12', '.pfx'}
PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github_token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}'),
    'api_key': re.compile(r'\bsk-[A-Za-z0-9_-]{20,}'),
    'google_account_identifier': re.compile(r'(?:ocid|customer_id|account_key)[=\s:\"\x27]+\d{8,}', re.I),
    'personal_local_path': re.compile(r'/Users/[A-Za-z0-9._-]+/|[A-Z]:[\\/]Users[\\/][A-Za-z0-9._-]+[\\/]'),
}


def inspect(path, content):
    name = PurePosixPath(path)
    problems = []
    if PRIVATE_FOLDERS.intersection(name.parts) or name.suffix.lower() in PRIVATE_SUFFIXES:
        problems.append('private_artifact')
    if name.name.startswith('.env') and name.name != '.env.example':
        problems.append('environment_file')
    if any(marker in name.name.lower() for marker in ('credentials', 'client_secret', 'service-account', 'token.json')):
        problems.append('credential_filename')
    for label, pattern in PATTERNS.items():
        if pattern.search(content):
            problems.append(label)
    return problems


def main():
    result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            cwd=ROOT, capture_output=True, check=True)
    paths = sorted(set(result.stdout.decode('utf-8').strip('\0').split('\0')) - {''})
    errors = []
    for path in paths:
        file = ROOT/path
        if file.is_symlink():
            errors.append((path, ['symlink_requires_review']))
            continue
        try:
            content = file.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append((path, ['binary_requires_review']))
            continue
        if problems := inspect(path, content):
            errors.append((path, problems))
    for path, problems in errors:
        # Never echo a matched secret.
        print(f'{path}: {", ".join(problems)}')
    if errors:
        raise SystemExit(1)
    print(f'{len(paths)} archivos públicos comprobados. Ningún patrón detectado; se requiere además revisión del contenido.')


if __name__ == '__main__':
    main()
