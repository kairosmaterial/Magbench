import json
import sys
import numpy as np
import pytest
from ase import Atoms
from magbench import cli
from magbench.dummy import DummyAdapter


def test_adapter_loading_and_units():
    assert cli.load_adapter('magbench.dummy:DummyAdapter') is DummyAdapter
    with pytest.raises(ValueError, match='module:Class'):
        cli.load_adapter('missing-colon')
    model = DummyAdapter(None)
    atoms = Atoms('Fe', cell=[3, 3, 3], pbc=True)
    assert model.energy(atoms, [2]) == 2
    np.testing.assert_array_equal(model.energy_gradient(atoms, [2])[1], [2])
    assert model.efs(atoms, [2])['forces'].shape == (1, 3)
    assert not model.supports_exchange_head()


def test_cli_records_adapter_and_guards_resume(tmp_path, monkeypatch):
    inputs = tmp_path / 'inputs'
    (inputs / 'ground_state').mkdir(parents=True)
    (inputs / 'manifest.json').write_text(json.dumps({'cohorts': {'ground_state': ['001']}}))
    (inputs / 'screening_sign_reference.json').write_text('{"001": {}}')
    (inputs / 'ground_state/001.json').write_text(json.dumps(dict(
        species=['Fe'], cell_A=np.eye(3).tolist(), fractional_positions=[[0, 0, 0]],
        magnetic_site_indices=[0])))
    checkpoint = tmp_path / 'dummy.pt'
    checkpoint.write_text('fixture')
    output = tmp_path / 'run'
    args = ['magbench', 'run', '--adapter', 'magbench.dummy:DummyAdapter',
            '--inputs', str(inputs), '--checkpoint', str(checkpoint),
            '--output', str(output), '--device', 'cpu', '--no-moment-head']
    monkeypatch.setattr(sys, 'argv', args)
    def search(model, atoms, *args):
        assert type(model) is DummyAdapter
        return {'energy_eV': model.energy(atoms, [2]), 'magmoms_muB': [2]}
    monkeypatch.setattr(cli, 'search_ground_state', search)
    cli.main()
    spec = 'magbench.dummy:DummyAdapter'
    assert cli.load(output / 'run.json')['adapter'] == spec
    assert cli.load(output / 'predictions.json')['001']['adapter'] == spec
    cli.main()
    args[args.index(spec)] = cli.DEFAULT_ADAPTER
    with pytest.raises(ValueError, match='Refusing to mix'):
        cli.main()
