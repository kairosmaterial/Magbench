"""Versioned rules, exclusions and published saved-prediction regressions."""
import json
import os
from pathlib import Path
import numpy as np
import pytest
from magbench.scoring import (evaluate, protocol_config, hull_side_credit,
                              parameter_error, DEFAULT_PROTOCOL_VERSION)
from leaderboard.cards import metrics_from

ROOT = Path(__file__).resolve().parents[1]


def test_exclusions_are_versioned_and_leave_reference_unchanged():
    dims = ('ground_state', 'hull', 'phonons', 'J', 'magnetovolume')
    cfg = {'cohorts': {d: ['001', '033', '080', '108', '194', '208'] for d in dims}}
    before = json.loads(json.dumps(cfg))
    legacy = protocol_config(cfg, '0.2.3')
    current = protocol_config(cfg, '0.3')
    assert cfg == before == legacy
    assert current['cohorts']['J'] == ['001']
    assert current['cohorts']['magnetovolume'] == ['001', '033', '080']
    for d in ('ground_state', 'hull', 'phonons'):
        assert current['cohorts'][d] == ['001', '033', '080', '108', '208']
    rules = json.loads((ROOT / 'benchmark_runner/magbench/protocols/0.3.json').read_text())
    assert all(x['reason'] and x['name'] for x in rules['exclusions'])
    assert DEFAULT_PROTOCOL_VERSION == '0.3'
    with pytest.raises(ValueError):
        protocol_config(cfg, 'unknown')


@pytest.mark.parametrize('model,reference,credit', [
    (.001, -.001, True), (.00100001, -.001, False),
    (.0005, -.002, False), (.002, .003, True),
    (0., .001, True), (0., .00100001, False), (-.002, 0., True)])
def test_hull_tolerance_requires_both_energies_near_boundary(model, reference, credit):
    assert hull_side_credit(model, reference, 1.) == credit
    assert hull_side_credit(model, reference) == ((model > 0) == (reference > 0))


def test_exchange_accuracy_scale_only_changes_accuracy():
    base = {'cohorts': {d: [] for d in ('ground_state', 'hull', 'phonons', 'J', 'magnetovolume')}, 'J': {'relative_scale': .2, 'absolute_floor_meV': .2,
             'sign_floor_meV': .2, 'sign_weight': .5, 'accuracy_weight': .5,
             'shell_weights': [3, 2.5, 2, 1.5, 1], 'outer_shell_weight': 1}}
    legacy = protocol_config(base, '0.2.3')['J']
    current = protocol_config(base, '0.3')['J']
    assert {k:v for k,v in current.items() if k not in ('relative_scale','absolute_floor_meV')} == {
        k:v for k,v in legacy.items() if k not in ('relative_scale','absolute_floor_meV')}
    for cfg, expected in [(legacy, 2.5), (current, 1.)]:
        assert parameter_error([.5, 3.], [0., 2.], cfg['relative_scale'],
                               cfg['absolute_floor_meV'], np.array([3., 1.])) == pytest.approx(expected)


@pytest.mark.parametrize('key', ['prophet-spin-v2l', 'prophet-spin-v1l',
                                 'prophet-spin-v1s', 'prophet-spin-v1s-6a'])
@pytest.mark.parametrize('version', ['0.2.3', '0.3'])
def test_saved_prediction_scores_both_versions(key, version):
    mapping = os.environ.get('MAGBENCH_LOCAL_PREDICTIONS')
    data = os.environ.get('MAGBENCH_DATA_DIR')
    if not mapping or not data:
        pytest.skip('External data and predictions required')
    prediction = Path(json.loads(Path(mapping).read_text())[key])
    got = evaluate(Path(data) / 'targets', json.loads(prediction.read_text()), prediction.parent,
                   protocol_version=version)
    filename = 'scores.json' if version == '0.3' else 'scores-v0.2.3.json'
    expected = json.loads((ROOT / 'models' / key / filename).read_text())
    assert got['total_score'] == expected['total_score']
    assert got['dimensions'] == expected['dimensions']
    if version == '0.3':
        removed = next(x for x in got['materials'] if x['id'] == '194')
        assert all(v is None for v in removed['scores'].values())
        assert removed['weighted_contribution_to_total'] == 0
        assert metrics_from(got)['ground_state_passes'] == sum(
            x['ground_state_pass'] for x in got['materials'] if x['id'] != '194')
        assert [got['dimensions'][d]['materials'] for d in got['dimensions']] == [190,190,111,167,131]
