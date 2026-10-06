"""Downloads the 120 benchmark instances and checks them against data/instances.csv (Python standard library only).

The instances with n = 100 and n = 500 come from the archive benchmark.zip distributed by Lai, Hao and Yue (2019),
and those with n = 1000 from the repository samehShihabi/MKMP-instances-1000 at a fixed commit
(data/instances_source.json). Every file must match its SHA-256 digest before it is written to instances/.

Usage:
    python scripts/download_instances.py
    python scripts/download_instances.py --archive benchmark.zip --dir1000 path/to/MKMP-instances-1000
"""
import argparse
import csv
import hashlib
import io
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fetch(urls):
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except OSError as exc:
            print(f'could not download {url}: {exc}')
    raise SystemExit('download failed; a local copy can be given with --archive or --dir1000')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--archive', type=Path, help='local copy of benchmark.zip (instances with n = 100 and n = 500)')
    ap.add_argument('--dir1000', type=Path, help='local copy of the repository MKMP-instances-1000')
    ap.add_argument('--out', type=Path, default=ROOT / 'instances')
    args = ap.parse_args()
    source = json.loads((ROOT / 'data' / 'instances_source.json').read_text(encoding='utf-8'))
    rows = list(csv.DictReader(open(ROOT / 'data' / 'instances.csv', newline='', encoding='utf-8')))
    archive, repository = source['archive'], source['repository']

    data = args.archive.read_bytes() if args.archive else fetch(archive['urls'])
    if sha256(data) != archive['sha256']:
        raise SystemExit('benchmark.zip: SHA-256 differs from data/instances_source.json')
    members = zipfile.ZipFile(io.BytesIO(data))

    args.out.mkdir(parents=True, exist_ok=True)
    written = 0
    for r in rows:
        if r['source'] == 'archive':
            content = members.read(r['source_path'])
        elif args.dir1000:
            content = (args.dir1000 / r['source_path']).read_bytes()
        else:
            content = fetch([repository['raw_url'].format(path=urllib.parse.quote(r['source_path']))])
        if sha256(content) != r['sha256']:
            raise SystemExit(f'{r["file"]}: SHA-256 differs from data/instances.csv')
        (args.out / r['file']).write_bytes(content)
        written += 1
    print(f'{written} instance files written to {args.out}, all matching their SHA-256 digests')


if __name__ == '__main__':
    main()
