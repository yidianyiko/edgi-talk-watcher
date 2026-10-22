"""Download or verify the pinned local Chinese ASR model; no credentials required."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def verified(path, entry):
    if not path.is_file() or path.stat().st_size != entry['bytes']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest() == entry['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'var/models/whisper-base')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'tools/asr_model.json').read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, entry in manifest['files'].items():
        path = args.output / name
        if not verified(path, entry):
            temporary = path.with_suffix('.part')
            url = f"https://huggingface.co/{manifest['repo']}/resolve/{manifest['revision']}/{name}"
            try:
                with urllib.request.urlopen(url, timeout=120) as source, temporary.open('wb') as target:
                    total = 0
                    while chunk := source.read(1024 * 1024):
                        total += len(chunk)
                        if total > entry['bytes']:
                            raise ValueError(f'Unexpected download size: {name}')
                        target.write(chunk)
                if not verified(temporary, entry):
                    raise ValueError(f'Model integrity check failed: {name}')
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        print(f'Verified {name}: {entry["bytes"]} bytes', flush=True)


if __name__ == '__main__':
    main()
