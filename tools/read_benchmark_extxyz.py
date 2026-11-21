#!/usr/bin/env python3
"""Read ELEMENTA-style benchmark frames without losing signed site moments.

Usage: python read_benchmark_extxyz.py benchmark_mp_aligned.extxyz
Python: from read_benchmark_extxyz import iter_frames
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
from ase.io import iread
from ase.io.extxyz import key_val_str_to_dict
from ase.calculators.singlepoint import SinglePointCalculator

PROPERTIES='species:S:1:pos:R:3:magmom:R:1'
INITIAL_PROPERTIES=PROPERTIES+':initial_magmom:R:1'
EXPERIMENTAL_PROPERTIES=PROPERTIES+':experimental_magmom:R:1'

def properties_parser(line):
    info=key_val_str_to_dict(line)
    assert info['Properties'] in (PROPERTIES,INITIAL_PROPERTIES,EXPERIMENTAL_PROPERTIES)
    # Distinguish the header's net magmom from the identically named atom column.
    fields=info['Properties'].split(':')
    for i in range(0,len(fields),3):
        if fields[i]=='magmom':fields[i]='atomic_magmom'
    info['Properties']=':'.join(fields)
    return info

def iter_frames(source):
    for atoms in iread(source,index=':',format='extxyz',properties_parser=properties_parser):
        moments=atoms.arrays['atomic_magmom']
        assert moments.shape==(len(atoms),) and np.isfinite(moments).all()
        results=atoms.calc.results.copy();results['magmoms']=moments.copy()
        # Set native initial moments before attaching the calculator, so ASE's
        # cached energy, forces and final magnetism remain valid.
        atoms.calc=None
        if 'initial_magmom' in atoms.arrays:
            initial=atoms.arrays['initial_magmom'];assert initial.shape==(len(atoms),) and np.isfinite(initial).all()
            atoms.set_initial_magnetic_moments(initial)
        atoms.calc=SinglePointCalculator(atoms,**results)
        yield atoms

def audit(path):
    frames=list(iter_frames(path)); seen=set()
    for a in frames:
        cid=int(a.info['benchmark_case_id']);assert cid not in seen;seen.add(cid)
        assert 'forces' not in a.calc.results and 'stress' not in a.calc.results
        assert 'initial_magmom' not in a.arrays
        assert np.isfinite(a.get_potential_energy()) and np.isfinite(a.get_magnetic_moments()).all()
        assert len(a.arrays['experimental_magmom'])==len(a)
    return dict(file=str(path),frames=len(frames),atoms=sum(len(a) for a in frames),energy_reference='J_static_experimental_reference',forces_included=False,stress_included=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('extxyz',type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=audit(args.extxyz);text=json.dumps(report,indent=2)
    if args.report:args.report.write_text(text+'\n')
    print(text)
