"""Refresh the site citation snapshot from an extracted benchmark dataset."""
import argparse
import hashlib
import json
from pathlib import Path


def export(data, output):
    snapshot = json.loads(output.read_text())
    rows = []
    for path in sorted((data / '01_refined_structures_191').glob('*/reference.json')):
        record = json.loads(path.read_text())
        references = [{key: item[key] for key in ('magndata_id', 'doi', 'title',
                      'authors', 'journal', 'volume', 'year', 'reference_scope')
                      if item.get(key) is not None}
                      for item in (record.get('references') or [])]
        rows.append(dict(id=f"{record['index']:03d}", formula=record['formula'],
                         phase=record.get('phase', ''), magndata_id=record.get('magndata_id'),
                         doi=record.get('doi'), references=references,
                         source=str(path.relative_to(data)),
                         source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if len(rows) != 191 or len({row['id'] for row in rows}) != 191:
        raise ValueError('Expected 191 distinct material references')
    snapshot['materials'] = rows
    output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('docs/material_references.json'))
    args = parser.parse_args()
    export(args.data, args.output)
