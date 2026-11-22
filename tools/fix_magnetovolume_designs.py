#!/usr/bin/env python3
"""Zero the sign entries on non-magnetic sites in the magnetovolume energy-mapping designs.

Every magnetovolume state is, on the magnetic sites, identical to a state of the exchange (J)
design of the same material and cell, with identical features. The entries on the remaining
sites are set to zero, which makes each magnetovolume state equal to that exchange state.
Usage: fix_magnetovolume_designs.py <inputs_dir> <output_dir>
"""
import json, sys, hashlib
from pathlib import Path
import numpy as np

src, out = Path(sys.argv[1]), Path(sys.argv[2])
(out / 'magnetovolume').mkdir(parents=True, exist_ok=True)
report = {}
for path in sorted((src / 'magnetovolume').glob('*.json')):
    raw = path.read_text()
    design = json.loads(raw)
    exchange = json.loads((src / 'exchange' / path.name).read_text())
    by_cell = {}
    for state in exchange['states']:
        by_cell.setdefault(state['cell'], []).append(state)
    changed_states = changed_entries = 0
    for state in design['states']:
        signs = np.asarray(state['signs'], float)
        candidates = by_cell[state['cell']]
        mask = np.zeros(len(signs), bool)
        for other in candidates:
            mask |= np.asarray(other['signs'], float) != 0
        fixed = np.where(mask, signs, 0.0)
        match = [other for other in candidates if np.array_equal(fixed, np.asarray(other['signs'], float))]
        if len(match) != 1:
            raise SystemExit(f'{path.name}: state is not a unique exchange-design state')
        if not np.allclose(state['features'], match[0]['features'], atol=1e-9, rtol=0):
            raise SystemExit(f'{path.name}: features differ from the exchange design')
        n = int(np.count_nonzero(fixed != signs))
        changed_states += n > 0
        changed_entries += n
        state['signs'] = match[0]['signs']
    text = json.dumps(design, **FORMAT) if (FORMAT := globals().get('FORMAT')) else None
    # keep the formatting of the source file: detect it once from the first file
    if text is None:
        for kwargs in ({}, {'separators': (',', ':')}, {'indent': 1}, {'indent': 2}, {'indent': 4}):
            if json.dumps(json.loads(raw), **kwargs) == raw.rstrip('\n'):
                FORMAT = kwargs
                break
        else:
            FORMAT = {'indent': 2}
            report['_format_note'] = 'source formatting not reproduced exactly; indent=2 used'
        text = json.dumps(design, **FORMAT)
    target = out / 'magnetovolume' / path.name
    target.write_text(text + ('\n' if raw.endswith('\n') else ''))
    report[path.stem] = dict(states=len(design['states']), changed_states=int(changed_states), changed_entries=changed_entries,
                             sha256_before=hashlib.sha256(raw.encode()).hexdigest(),
                             sha256_after=hashlib.sha256(target.read_bytes()).hexdigest())
(out / 'magnetovolume_fix_report.json').write_text(json.dumps(report, indent=1) + '\n')
materials = [k for k in report if not k.startswith('_')]
print('materials', len(materials), 'states', sum(report[k]['states'] for k in materials),
      'changed states', sum(report[k]['changed_states'] for k in materials),
      'changed entries', sum(report[k]['changed_entries'] for k in materials), 'format', FORMAT)
