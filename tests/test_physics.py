"""CPU physics contracts using analytic models and fixed synthetic designs."""
import itertools
import numpy as np
import pytest
from ase import Atoms
from magbench.physics import (DEFAULTS, fit_exchange, magnetic_seeds,
    magnetic_screening_seeds, SpinCalculator, SpinCellFilter, phonons)


class Heisenberg:
    def energy(self, atoms, moments):
        s = np.sign(moments)
        return -6.7 + .012 * s[0] * s[1] - .004 * s[1] * s[2]


def design():
    geometry = dict(species=['Fe'] * 3, cell_A=(np.eye(3) * 8).tolist(),
                    fractional_positions=[[0, 0, 0], [.2, 0, 0], [.4, 0, 0]])
    states = []
    for tail in itertools.product((1, -1), repeat=2):
        s = [1, *tail]
        states.append(dict(cell='a', signs=s, starting_moments_muB=s,
                           features=[s[0] * s[1], s[1] * s[2]]))
    return dict(offset_cells=['a'], geometries={'a': geometry}, states=states)


def test_mapping_recovers_signed_exchange_and_checks_rank():
    d = design()
    np.testing.assert_allclose(fit_exchange(Heisenberg(), d, DEFAULTS), [12, -4], atol=1e-10)
    d['states'] = d['states'][:2]
    with pytest.raises(ValueError, match='not full rank'):
        fit_exchange(Heisenberg(), d, DEFAULTS)


@pytest.mark.parametrize('n', [0, 1, 2, 6])
def test_seed_enumeration_order(n):
    actual = list(magnetic_seeds(n, DEFAULTS))
    expected = [np.empty(0)] if n == 0 else [
        [1, *tail] for tail in itertools.product((1, -1), repeat=n - 1)]
    np.testing.assert_array_equal(actual, expected)


def test_large_seed_space_is_deterministic_unique_and_reference_reserved():
    seeds = np.asarray(list(magnetic_seeds(9, DEFAULTS)))
    assert seeds.shape == (32, 9)
    assert np.all(seeds[:, 0] == 1)
    assert len(set(map(tuple, seeds))) == 32
    np.testing.assert_array_equal(seeds, list(magnetic_seeds(9, DEFAULTS)))
    other = list(magnetic_seeds(9, dict(DEFAULTS, seed=123)))
    assert not np.array_equal(seeds[1:], other[1:])
    absent = next(np.array([1, *tail]) for tail in itertools.product((1, -1), repeat=8)
                  if tuple([1, *tail]) not in set(map(tuple, seeds)))
    pooled = magnetic_screening_seeds(9, DEFAULTS, {'reference_signs': -absent})
    np.testing.assert_array_equal(pooled[:-1], seeds[:-1])
    np.testing.assert_array_equal(pooled[-1], absent)


class Toy:
    def energy_gradient(self, atoms, moments):
        m = np.asarray(moments)
        return float(.5 * np.sum(m * m)), m

    def efs(self, atoms, moments):
        return dict(energy=self.energy_gradient(atoms, moments)[0],
                    forces=np.zeros((len(atoms), 3)), stress=np.zeros(6))


def test_spin_cell_force_matches_finite_difference_and_projects_bound():
    a = Atoms('Fe2', positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True)
    a.set_initial_magnetic_moments([1.3, -.7])
    a.calc = SpinCalculator(Toy())
    f = SpinCellFilter(a, 2, [0, 1])
    x = f.get_positions()
    forces = f.get_forces()
    for i in range(len(a) + 3, len(f)):
        h = 1e-6
        plus, minus = x.copy(), x.copy()
        plus[i, 0] += h
        minus[i, 0] -= h
        f.set_positions(plus)
        ep = a.get_potential_energy()
        f.set_positions(minus)
        em = a.get_potential_energy()
        assert forces[i, 0] == pytest.approx(-(ep - em) / (2 * h), abs=1e-8)
    f.set_positions(x)
    a.set_initial_magnetic_moments([2, -2])
    # Inward restoring forces remain active at the bound.
    np.testing.assert_allclose(f.get_forces()[-2:, 0], [-4, 4])
    x[-2:, 0] = [3, -3]
    f.set_positions(x)
    np.testing.assert_array_equal(a.get_initial_magnetic_moments(), [2, -2])


def test_small_frozen_moment_phonon_path():
    pytest.importorskip('phonopy')
    unit = dict(species=['Fe'], cell_A=(np.eye(3) * 3).tolist(),
                fractional_positions=[[0, 0, 0]], magnetic_signs=[1], masses_amu=[55.845])
    definition = dict(unitcell=unit, supercell_matrix=np.eye(3, dtype=int),
                      primitive_matrix=np.eye(3), symmetry_tolerance_A=1e-5,
                      frequency_conversion_factor=15.6333, displacement_distance_A=.01)
    a = Atoms('Fe', cell=[3, 3, 3], pbc=True)
    a.set_initial_magnetic_moments([2])
    sampling = {kind + '_qpoints': np.array([[0, 0, 0], [.5, 0, 0]]) for kind in ('mesh', 'band')}
    result = phonons(Toy(), definition, sampling, DEFAULTS, relaxed=a)
    assert result['displacement_count'] > 0
    for kind in ('mesh', 'band'):
        assert result[kind + '_frequencies_THz'].shape == (2, 3)
        np.testing.assert_allclose(result[kind + '_frequencies_THz'], 0, atol=1e-12)
        np.testing.assert_array_equal(result[kind + '_qpoints'], sampling[kind + '_qpoints'])
