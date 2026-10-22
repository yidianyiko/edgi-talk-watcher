"""Package an explicit text-source allowlist, never reading private configurations."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'artifacts/submission'
TREES = ('watcher', 'tools', 'firmware', 'tests', 'docs')
EXTENSIONS = {'.py', '.ps1', '.sh', '.c', '.h', '.patch', '.json', '.js', '.mjs',
              '.cjs', '.css', '.html', '.md', '.txt'}
IGNORED_PARTS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'node_modules', '.git'}
CREDENTIAL_ASSIGNMENT = re.compile(
    r'(?im)^\s*(?:export\s+)?(?:JEV_TOKEN|WIFI_PASSWORD|BOARD_GATEWAY_TOKEN)\s*=\s*'
    r'[\"\']?([A-Za-z0-9_+/.=-]{20,})'
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = [ROOT/'AGENTS.md', ROOT/'CONTEXT.md', ROOT/'README.md'] + sorted(ROOT.glob('requirements*.txt'))
    files += sorted((ROOT/'research').glob('*.py'))
    skipped_cache_files = 0
    for tree in TREES:
        for path in sorted((ROOT/tree).rglob('*')):
            relative = path.relative_to(ROOT)
            if any(part in IGNORED_PARTS for part in relative.parts) or path.suffix == '.pyc':
                if path.is_file():
                    skipped_cache_files += 1
                continue
            if path.is_dir():
                continue
            if path.is_symlink():
                raise ValueError(f'Symlink outside source policy: {relative}')
            if path.suffix not in EXTENSIONS or any(part.startswith('.env') for part in relative.parts):
                raise ValueError(f'Unrecognized source path: {relative}')
            files.append(path)
    payloads = {}
    entries = []
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        if name.split('/')[0] not in set(TREES) | {'AGENTS.md', 'CONTEXT.md', 'README.md', 'research'} and not re.fullmatch(r'requirements[^/]*\.txt', name):
            raise ValueError(f'Path outside allowlist: {name}')
        data = path.read_bytes()
        text = data.decode('utf-8')
        if '\0' in text:
            raise ValueError(f'Binary content forbidden: {name}')
        if CREDENTIAL_ASSIGNMENT.search(text):
            raise ValueError(f'Credential-shaped assignment requires review in: {name}; value withheld')
        payloads[name] = data
        entries.append({'path': name, 'bytes': len(data), 'sha256': sha(data)})
    manifest = {
        'kind': 'source-only snapshot', 'created_on': '2026-10-22',
        'roots': list(TREES) + ['research/*.py'], 'files': entries,
        'excluded': ['vendor/', 'var/', '.env*', 'artifacts/', 'testdata/',
                     'research/fixtures/', 'compiled binaries', 'generated caches', 'raw recordings and scenes'],
        'credential_scope_check': 'only allowlisted text scanned; private values not read or reported',
        'bsp_revision': 'b135be8a28127e276a04b70d27950c3ba07b917a',
        'fixture_limit': 'testdata excluded; fixture-dependent tests need separate reviewed fixtures',
    }
    encoded = (json.dumps(manifest, indent=2)+'\n').encode()
    package = OUT/'source.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
        archive.writestr('SOURCE-MANIFEST.json', encoded)
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(payloads) | {'SOURCE-MANIFEST.json'}
        for entry in entries:
            assert sha(archive.read(entry['path'])) == entry['sha256']
        assert not any(n.split('/')[0] in {'vendor', 'var', 'artifacts', 'testdata'}
                       or any(p.startswith('.env') or p in IGNORED_PARTS for p in Path(n).parts)
                       for n in archive.namelist())
    (OUT/'source-manifest.json').write_bytes(encoded)
    report = {'created_on': '2026-10-22', 'zip_integrity': 'pass',
              'source_files': len(entries), 'cache_files_excluded': skipped_cache_files,
              'source_payload_sha256_matches': True, 'allowlist_scope': 'pass',
              'credential_shape_scan': 'pass; private files not opened',
              'archive_bytes': package.stat().st_size, 'archive_sha256': sha(package.read_bytes())}
    (OUT/'source-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
