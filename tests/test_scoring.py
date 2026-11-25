import json
import os
from pathlib import Path
import numpy as np
import pytest
from magbench.scoring import continuous,ground_alignment,select_ground_candidate,parameter_error
from leaderboard.cards import ROOT,read,compare,metrics_from
from leaderboard.validation import validate


def test_ground_symmetry_global_flip_and_moment_tolerance():
    target={'magnetic_site_indices':[0,1],'reference_signs':[1,-1],'minimum_abs_moment_muB':[.1,.2],'symmetry_permutations':[[0,1],[1,0]],'reference_magmoms_muB':[1,-2]}
    assert ground_alignment({'magmoms_muB':[-1.25,2.5]},target,2) is not None
    assert ground_alignment({'magmoms_muB':[2,-1]},target,2) is not None
    assert ground_alignment({'magmoms_muB':[-1.251,2.5]},target,2) is None
    assert ground_alignment({'magmoms_muB':[1,-2],'reference_periodicity_match':False},target,2) is None


def test_one_mev_per_atom_window_is_inclusive():
    target={'magnetic_site_indices':[0],'reference_signs':[1],'minimum_abs_moment_muB':[.1],'symmetry_permutations':[[0]],'reference_magmoms_muB':[1]}
    bad={'energy_eV':0.,'seed_index':0,'magmoms_muB':[.01]}
    good={'energy_eV':.001,'seed_index':1,'magmoms_muB':[1.]}
    assert select_ground_candidate({'converged_candidates':[bad,good]},target,1)[0] is good
    good['energy_eV']=.001001
    assert select_ground_candidate({'converged_candidates':[bad,good]},target,1)==(None,None)


def test_error_constants_and_saturation():
    assert continuous(1)==.5
    assert continuous(2000)==0.
    assert parameter_error([.2,2.4],[0,2],.2,.2)==pytest.approx(1.)


@pytest.mark.parametrize('key',['prophet-spin-v1s','prophet-spin-v1l','prophet-spin-v2l','prophet-spin-v1s-6a'])
def test_full_local_replay_when_inputs_supplied(key):
    mapping=os.environ.get('MAGBENCH_LOCAL_PREDICTIONS')
    data=os.environ.get('MAGBENCH_DATA_DIR')
    if not mapping or not data:pytest.skip('Local replay needs external data and predictions; no prediction artefacts are tracked')
    prediction=json.loads(Path(mapping).read_text())[key]
    result=validate(key,offline=True,data=Path(data),predictions=Path(prediction))
    assert result.passed,result.markdown()
    checks={r['check']:r['status'] for r in result.rows}
    assert checks['Scorer replay']==checks['Replay equals scores.json']==checks['Replay equals declared metrics']=='PASS'


def test_ground_exception_is_recorded_without_changing_gate(tmp_path):
    from magbench.scoring import evaluate
    from leaderboard.validation import compare_replay
    cfg = {'cohorts': {k: ['001'] for k in ('ground_state', 'hull', 'phonons', 'J', 'magnetovolume')},
           'dimension_weights': {k: .2 for k in ('ground_state', 'hull', 'phonons', 'J', 'magnetovolume')}}
    # Use the actual public scoring configuration shape, with a one-material cohort.
    source = json.loads((ROOT / 'models/prophet-spin-v1s/scores.json').read_text())
    reference = {'magnetic_site_indices': [0], 'reference_signs': [1],
                 'minimum_abs_moment_muB': [.1], 'symmetry_permutations': [[0]],
                 'reference_magmoms_muB': [1]}
    for name, value in [('scoring', cfg), ('ground_state', {'001': reference}),
                        ('hull', {'001': {'natoms': 1}}),
                        ('materials', [{'id': '001', 'name': 'Fe'}])]:
        (tmp_path / (name + '.json')).write_text(json.dumps(value))
    # The evaluator reads weights from a separate key; match its public contract.
    cfg['weights'] = cfg.pop('dimension_weights')
    (tmp_path / 'scoring.json').write_text(json.dumps(cfg))
    got = evaluate(tmp_path, {'001': {'magmoms_muB': []}}, tmp_path)
    row = got['materials'][0]
    assert got['total_score'] == 0
    assert row['details']['ground_state']['failed']
    old = json.loads(json.dumps(got))
    del old['materials'][0]['details']['ground_state']
    compare_replay(got, old)
    old['total_score'] = .1
    with pytest.raises(ValueError):
        compare_replay(got, old)
