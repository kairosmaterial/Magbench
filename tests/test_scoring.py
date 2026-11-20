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


@pytest.mark.parametrize('key',['prophet-spin-ex','prophet-spin-v2'])
def test_full_local_replay_when_inputs_supplied(key):
    mapping=os.environ.get('MAGBENCH_LOCAL_PREDICTIONS')
    data=os.environ.get('MAGBENCH_DATA_DIR')
    if not mapping or not data:pytest.skip('Local replay needs external data and predictions; no prediction artefacts are tracked')
    prediction=json.loads(Path(mapping).read_text())[key]
    result=validate(key,offline=True,data=Path(data),predictions=Path(prediction))
    assert result.passed,result.markdown()
    checks={r['check']:r['status'] for r in result.rows}
    assert checks['Scorer replay']==checks['Replay equals scores.json']==checks['Replay equals declared metrics']=='PASS'
