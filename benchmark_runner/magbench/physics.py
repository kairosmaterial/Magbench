"""Magnetic sign screening, energy mapping and finite displacements."""
import itertools
import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator,all_changes
from ase.filters import FrechetCellFilter
from ase.optimize import FIRE

MAX_RELAX_STEPS = 500
PHONON_RELAX_FMAX = .01
PHONON_RELAX_MAX_STEPS = 500

DEFAULTS=dict(seed=20261118,search_states=32,mag_steps=500,mag_lr=.04,mag_tol=1e-3,moment_bound=8.,fmax=.05,relax_steps=MAX_RELAX_STEPS,energy_tol_eV=.001,moment_delta_tol=.05,amplitude=3.)

def atoms_from(d):
    return Atoms(d['species'],cell=d['cell_A'],scaled_positions=d['fractional_positions'],pbc=True)

def optimize_moments(model,atoms,initial,cfg,signs=None):
    x=np.asarray(initial,float).copy()
    if signs is not None and hasattr(model,'initial_moments'):x=model.initial_moments(atoms,x,signs)
    lower=np.full(len(x),-cfg['moment_bound']);upper=-lower
    if signs is not None:
        signs=np.asarray(signs);lower[signs>0]=0.;upper[signs<0]=0.;lower[signs==0]=0.;upper[signs==0]=0.
    x=np.clip(x,lower,upper);mt=np.zeros_like(x);vt=mt.copy();best=None
    prepare = getattr(model, 'prepare_energy_gradient', None)
    gradient = prepare(atoms) if prepare else lambda moments: model.energy_gradient(atoms, moments)
    for step in range(cfg['mag_steps']+1):
        energy,grad=gradient(x)
        if not np.isfinite(energy) or not np.isfinite(grad).all(): raise ValueError('Nonfinite magnetic derivative')
        projected=grad.copy();projected[(x<=lower+1e-8)&(grad>0)]=0.;projected[(x>=upper-1e-8)&(grad<0)]=0.
        norm=float(np.max(abs(projected)));item=(energy,x.copy(),norm)
        if best is None or energy<best[0]:best=item
        if norm<=cfg['mag_tol']:return dict(energy=energy,moments=x,gradient=norm,converged=True,steps=step)
        if step==cfg['mag_steps']:break
        t=step+1;mt=.9*mt+.1*grad;vt=.999*vt+.001*grad**2
        x=np.clip(x-cfg['mag_lr']*(mt/(1-.9**t))/(np.sqrt(vt/(1-.999**t))+1e-8),lower,upper)
    return dict(energy=best[0],moments=best[1],gradient=best[2],converged=False,steps=cfg['mag_steps'])

class SpinCalculator(Calculator):
    implemented_properties = ['energy', 'forces', 'stress']

    def __init__(self, model, relax_magnetic_moments=True):
        super().__init__()
        self.model = model
        self.relax_magnetic_moments = relax_magnetic_moments

    def calculate(self, atoms=None, properties=('energy',), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        moments = atoms.get_initial_magnetic_moments()
        joint = getattr(self.model, 'joint_efs', None)
        if self.relax_magnetic_moments and joint:
            self.results = joint(atoms, moments)
        else:
            self.results = self.model.efs(atoms, moments)
            if self.relax_magnetic_moments:
                _, gradient = self.model.energy_gradient(atoms, moments)
                self.results['moment_gradient'] = gradient
        if any(not np.isfinite(value).all() for value in self.results.values()):
            raise ValueError('Nonfinite model energy or derivative during relaxation')


class SpinCellFilter(FrechetCellFilter):
    """Append a scaled collinear moment coordinate for each magnetic site."""

    def __init__(self, atoms, moment_bound, magnetic_indices):
        super().__init__(atoms)
        self.magnetic_indices = np.asarray(magnetic_indices, dtype=int)
        self.moment_bound = moment_bound
        self.moment_scale = 0.5  # optimizer-coordinate Å per μB

    def __len__(self):
        return len(self.atoms) + len(self.magnetic_indices) + 3

    def get_positions(self):
        magnetic = np.zeros((len(self.magnetic_indices), 3))
        magnetic[:, 0] = self.atoms.get_initial_magnetic_moments()[self.magnetic_indices] * self.moment_scale
        return np.vstack([super().get_positions(), magnetic])

    def set_positions(self, positions, **kwargs):
        split = len(self.atoms) + 3
        super().set_positions(positions[:split], **kwargs)
        moments = np.zeros(len(self.atoms))
        variable_moments = positions[split:, 0] / self.moment_scale
        moments[self.magnetic_indices] = np.clip(variable_moments, -self.moment_bound, self.moment_bound)
        self.atoms.set_initial_magnetic_moments(moments)

    def get_forces(self, **kwargs):
        structure = super().get_forces(**kwargs)
        moments = self.atoms.get_initial_magnetic_moments()[self.magnetic_indices]
        spin_force = -self.atoms.calc.results['moment_gradient'][self.magnetic_indices] / self.moment_scale
        spin_force[(moments >= self.moment_bound) & (spin_force > 0)] = 0
        spin_force[(moments <= -self.moment_bound) & (spin_force < 0)] = 0
        magnetic = np.zeros((len(self.magnetic_indices), 3))
        magnetic[:, 0] = spin_force
        return np.vstack([structure, magnetic])


def magnetic_seeds(n, cfg):
    limit = min(32, cfg['search_states'])
    if n == 0:
        yield np.empty(0)
    elif n <= 6:
        # Fix the first sign because one global reversal is equivalent.
        for tail in itertools.islice(itertools.product((1, -1), repeat=n-1), limit):
            yield np.array((1, *tail), dtype=float)
    else:
        rng = np.random.default_rng(cfg['seed'])
        seen = {(1,) * n}
        yield np.ones(n)
        while len(seen) < limit:
            signs = (1, *rng.choice((1, -1), size=n-1))
            if signs not in seen:
                seen.add(signs)
                yield np.array(signs, dtype=float)


def magnetic_screening_seeds(n, cfg, reference):
    """Keep the existing seed order and reserve a slot for the reference signs."""
    seeds = list(magnetic_seeds(n, cfg))
    signs = np.asarray(reference['reference_signs'], dtype=float)
    if signs.shape != (n,) or n < 1 or not np.isin(signs, (-1, 1)).all():
        raise ValueError('Expected one reference sign (+/-1) per magnetic site')
    if not seeds or cfg['search_states'] < 1:
        raise ValueError('At least one screening state is required')
    signs = signs * signs[0]
    if not any(np.array_equal(seed, signs) for seed in seeds):
        seeds[-1] = signs
    return seeds


def screening_sign_match(signs, reference):
    signs = np.asarray(signs)
    target = np.asarray(reference['reference_signs'])
    return any(np.array_equal(signs, target[perm]) or np.array_equal(signs, -target[perm])
               for perm in reference['symmetry_permutations'])


class ScreeningSignFailure(RuntimeError):
    def __init__(self, screening):
        super().__init__('No experimental sign-equivalent state in the top-three screening energies')
        self.screening = screening


def relax_candidate(model, atoms, moments, cfg, progress, magnetic_indices=None):
    a = atoms.copy()
    bound = cfg['moment_bound']
    magnetic_indices = np.arange(len(a)) if magnetic_indices is None else np.asarray(magnetic_indices, dtype=int)
    initial_moments = np.zeros(len(a))
    initial_moments[magnetic_indices] = np.clip(np.asarray(moments)[magnetic_indices], -bound, bound)
    a.set_initial_magnetic_moments(initial_moments)
    a.calc = SpinCalculator(model)
    cell_filter = SpinCellFilter(a, bound, magnetic_indices)
    previous = None
    descriptor = {}
    max_steps = min(MAX_RELAX_STEPS, cfg['relax_steps'])
    with FIRE(cell_filter, logfile=None) as optimizer:
        for step in range(max_steps + 1):
            forces = cell_filter.get_forces()
            energy = float(a.get_potential_energy())
            m = a.get_initial_magnetic_moments()
            fmax = float(np.linalg.norm(a.get_forces(), axis=1).max())
            cell_force = float(np.linalg.norm(forces[len(a):len(a)+3], axis=1).max())
            de = None if previous is None else abs(energy - previous[0])
            dm = None if previous is None else float(np.max(abs(m - previous[1])))
            descriptor = dict(relax_steps=step, fmax=fmax, cell_force=cell_force,
                              delta_energy_eV=de, delta_energy_eV_atom=None if de is None else de/len(a),
                              delta_moment_muB=dm)
            if step % 25 == 0:
                progress(**descriptor)
            if (de is not None and max(fmax, cell_force) < cfg['fmax']
                    and de < cfg['energy_tol_eV'] and dm < cfg['moment_delta_tol']):
                return dict(energy_eV=energy, magmoms_muB=m.tolist(),
                            positions_A=a.positions.tolist(), cell_A=a.cell.array.tolist(), **descriptor)
            if step == max_steps:
                break
            previous = (energy, m)
            optimizer.step()
    raise RuntimeError(f'Joint relaxation did not converge: {descriptor}')


def search_ground_state(model, atoms, cfg, active_indices=None, sign_reference=None):
    active = np.arange(len(atoms)) if active_indices is None else np.asarray(active_indices, int)
    inactive = np.ones(len(atoms), dtype=bool)
    inactive[active] = False
    progress = getattr(model, 'progress', lambda **_: None)
    if sign_reference is None:
        seeds = list(magnetic_seeds(len(active), cfg))
    else:
        if not np.array_equal(active, sign_reference['magnetic_site_indices']):
            raise ValueError('Reference sign ordering differs from the magnetic site list')
        seeds = magnetic_screening_seeds(len(active), cfg, sign_reference)
    candidates = []
    for seed_id, signs in enumerate(seeds):
        progress(detail='sign_search', state=seed_id+1)
        seed = np.zeros(len(atoms))
        seed[active] = signs * cfg['amplitude']
        if getattr(model, 'moment_predictor', None) is not None:
            # Preserve candidate signs. The head sets starting magnitudes.
            moments = model.initial_moments(atoms, seed, np.sign(seed))
        else:
            approximate = optimize_moments(model, atoms, seed, cfg, signs=np.sign(seed))
            moments = approximate['moments']
        moments = np.clip(moments, -cfg['moment_bound'], cfg['moment_bound'])
        moments[inactive] = 0.0
        energy_function = getattr(model, 'energy', None)
        energy = energy_function(atoms, moments) if energy_function else model.energy_gradient(atoms, moments)[0]
        if not np.isfinite(energy):
            raise ValueError(f'Nonfinite screening energy for sign state {seed_id}')
        candidates.append((energy, seed_id, moments))

    shortlisted = sorted(candidates, key=lambda c: (c[0], c[1]))[:3]
    screening = {'states_screened': len(candidates), 'shortlist': []}
    for energy, seed_id, moments in shortlisted:
        signs = np.sign(moments[active]).astype(int)
        matched = sign_reference is not None and screening_sign_match(signs, sign_reference)
        screening['shortlist'].append(dict(seed_index=seed_id, energy_eV=energy,
                                           signs=signs.tolist(), reference_sign_match=matched))
    if sign_reference is not None and not any(row['reference_sign_match'] for row in screening['shortlist']):
        progress(detail='screening_sign_failed', **screening)
        raise ScreeningSignFailure(screening)

    converged = []
    failures = []
    for rank, (energy, seed_id, moments) in enumerate(shortlisted, 1):
        def report(**detail):
            progress(detail='joint_relaxation', rank=rank, seed=seed_id, **detail)
        try:
            result = relax_candidate(model, atoms, moments, cfg, report, magnetic_indices=active)
            converged.append(dict(result, seed_index=seed_id, screening_energy_eV=energy))
        except (ValueError, RuntimeError) as exc:
            failures.append(dict(seed_index=seed_id, screening_rank=rank, error=str(exc)))
    if not converged:
        raise RuntimeError(f'No top-three candidate converged: {failures}')
    return dict(min(converged, key=lambda r: r['energy_eV']),
                **screening, candidates_converged=len(converged),
                converged_candidate_steps=[r['relax_steps'] for r in converged],
                converged_candidates=converged,
                failed_candidates=failures)


def relaxed_atoms(initial, result):
    atoms = atoms_from(initial)
    atoms.set_cell(result['cell_A'])
    atoms.set_positions(result['positions_A'])
    atoms.set_initial_magnetic_moments(result['magmoms_muB'])
    return atoms


def dft_exchange_atoms(initial, unitcell, moments):
    """Build the original DFT cell in the atom order of the periodic bond catalog."""
    if unitcell['species'] != initial['species']:
        raise ValueError('Exchange atom order differs from the ground-state input')
    if not np.allclose(unitcell['cell_A'], initial['cell_A'], atol=1e-5, rtol=1e-5):
        raise ValueError('Exchange lattice differs from the ground-state input')
    difference = np.asarray(unitcell['fractional_positions']) - np.asarray(initial['fractional_positions'])
    if not np.allclose(difference, np.rint(difference), atol=1e-5, rtol=0):
        raise ValueError('Exchange sites differ from the ground-state input')
    atoms = atoms_from(unitcell)
    atoms.set_initial_magnetic_moments(moments)
    return atoms


def dft_exchange_design(design, initial, moments):
    """Map the DFT moment magnitudes onto the unchanged DFT design geometries."""
    original = atoms_from(initial)
    original_frac = original.get_scaled_positions(wrap=False)
    initial_species = np.asarray(original.get_chemical_symbols())
    maps = {}
    for key, geometry in design['geometries'].items():
        lattice = np.asarray(geometry['cell_A']) @ np.linalg.inv(original.cell.array)
        transfer = np.rint(lattice).astype(int)
        if not np.allclose(lattice, transfer, atol=3e-3, rtol=0):
            raise ValueError(f'Exchange cell {key} is incommensurate with the supplied cell')
        fractional = np.asarray(geometry['fractional_positions']) @ transfer
        delta = fractional[:, None, :] - original_frac
        residual = (delta - np.rint(delta)) @ original.cell.array
        distance = np.linalg.norm(residual, axis=2)
        distance[np.asarray(geometry['species'])[:, None] != initial_species] = np.inf
        sites = distance.argmin(axis=1)
        if not np.all(distance[np.arange(len(sites)), sites] < .25):
            raise ValueError(f'Exchange cell {key} could not be matched to original atomic sites')
        maps[key] = sites
    amplitudes = abs(np.asarray(moments, dtype=float))
    states = [dict(state, starting_moments_muB=(np.asarray(state['signs']) * amplitudes[maps[state['cell']]]).tolist())
              for state in design['states']]
    return dict(design, states=states)


def fit_exchange(model,design,cfg,volume_delta=0.):
    offsets=design['offset_cells'];xs=[];ys=[]
    for state_index,state in enumerate(design['states']):
        if hasattr(model,'progress'):model.progress(detail='energy_mapping',state=state_index,states=len(design['states']),volume_delta=volume_delta)
        a=atoms_from(design['geometries'][state['cell']]);a.set_cell(a.cell*(1+volume_delta)**(1/3),scale_atoms=True)
        signs = np.asarray(state['signs'], float)
        if 'starting_moments_muB' in state:
            moments = np.asarray(state['starting_moments_muB'])
            if np.any(abs(moments[signs!=0]) < .001):
                raise RuntimeError('DFT amplitudes do not support this exchange design')
            energy = model.energy(a, moments)
        else:
            spin = optimize_moments(model, a, signs*cfg['amplitude'], cfg, signs=signs)
            if not spin['converged']:
                raise RuntimeError('Magnetic energy mapping did not converge')
            if np.any(abs(spin['moments'][signs!=0]) < .001):
                raise RuntimeError('Requested energy-mapping branch collapsed')
            energy = spin['energy']
        xs.append([float(c==state['cell']) for c in offsets]+list(np.array(state['features'])/len(a)))
        ys.append(energy/len(a))
    X=np.asarray(xs);Y=np.asarray(ys);scale=np.maximum(np.linalg.norm(X,axis=0),1e-12)
    if np.linalg.matrix_rank(X/scale,tol=1e-9)!=X.shape[1]:raise ValueError('Energy mapping not full rank')
    coef=np.linalg.lstsq(X/scale,Y,rcond=1e-10)[0]/scale
    return coef[len(offsets):]*1000

def volume_exchange(model,design,cfg):
    # Separate matched zero-strain design; never substitute a different J fit.
    j0=fit_exchange(model,design,cfg);deltas=design['volume_deltas'];x=np.log1p(deltas)
    values=np.asarray([fit_exchange(model,design,cfg,d)-j0 for d in deltas])
    return np.linalg.lstsq(np.stack([x,x*x],axis=1),values,rcond=None)[0][0]

def relax_phonon_geometry(model, selected_atoms):
    """Refine positions and cell at fixed model moments before finite displacements."""
    atoms = selected_atoms.copy()
    atoms.calc = SpinCalculator(model, relax_magnetic_moments=False)
    cell_filter = FrechetCellFilter(atoms)
    progress = getattr(model, 'progress', lambda **_: None)

    with FIRE(cell_filter, logfile=None) as optimizer:
        for step in range(PHONON_RELAX_MAX_STEPS + 1):
            forces = cell_filter.get_forces()
            fmax = float(np.linalg.norm(atoms.get_forces(), axis=1).max())
            cell_force = float(np.linalg.norm(forces[len(atoms):], axis=1).max())
            converged = max(fmax, cell_force) < PHONON_RELAX_FMAX
            terminal = converged or step == PHONON_RELAX_MAX_STEPS
            state = dict(steps=step, fmax_eV_A=fmax, cell_force=cell_force, converged=converged)
            if terminal or step % 25 == 0:
                progress(detail='phonon_relaxation', **state)
            if terminal:
                return atoms, dict(state, positions_A=atoms.positions.tolist(),
                                   cell_A=atoms.cell.array.tolist())
            optimizer.step()


def phonons(model,definition,sampling,cfg,relaxed=None):
    from phonopy import Phonopy
    from phonopy.structure.atoms import PhonopyAtoms
    from spglib.error import SpglibError
    unit = definition['unitcell']
    if relaxed is None:
        atoms = atoms_from(unit)
        moments = np.asarray(unit['magnetic_signs'], float)
    else:
        atoms = relaxed
        if atoms.get_chemical_symbols() != unit['species']:
            raise ValueError('Phonon input ordering differs from the relaxed cell')
        moments = atoms.get_initial_magnetic_moments()
    unitcell = PhonopyAtoms(symbols=unit['species'], cell=atoms.cell.array,
                           scaled_positions=atoms.get_scaled_positions(), masses=unit['masses_amu'],
                           magnetic_moments=moments)
    phonopy_settings = dict(supercell_matrix=definition['supercell_matrix'],
                            primitive_matrix=definition['primitive_matrix'],
                            symprec=definition['symmetry_tolerance_A'])
    symmetry_reduced = True
    try:
        p = Phonopy(unitcell, **phonopy_settings)
    except SpglibError as exc:
        if str(exc) != 'spacegroup search failed':
            raise
        # Preserve the actual relaxed cell and enumerate displacements without point-group reduction.
        symmetry_reduced = False
        p = Phonopy(unitcell, is_symmetry=False, **phonopy_settings)
    p.unit_conversion_factor=definition['frequency_conversion_factor']
    p.generate_displacements(distance=definition['displacement_distance_A'])
    forces=[]
    if relaxed is not None:
        sc = p.supercell
        a = Atoms(sc.symbols, positions=sc.positions, cell=sc.cell, pbc=True)
        residual_forces = np.asarray(model.efs(a, sc.magnetic_moments)['forces'])
    for displacement_index,sc in enumerate(p.supercells_with_displacements):
        if hasattr(model,'progress'):model.progress(detail='phonon_displacement',displacement=displacement_index,displacements=len(p.supercells_with_displacements))
        a = Atoms(sc.symbols, positions=sc.positions, cell=sc.cell, pbc=True)
        if relaxed is not None:
            # Differentiate on the final magnetic configuration at fixed moments.
            forces_at_displacement = np.asarray(model.efs(a, sc.magnetic_moments)['forces'])
            f = forces_at_displacement - residual_forces
        else:
            sg = np.sign(sc.magnetic_moments)
            spin = optimize_moments(model, a, sg*cfg['amplitude'], cfg, signs=sg)
            if not spin['converged']:
                raise RuntimeError('Phonon spin branch failed to converge')
            if np.any(abs(spin['moments'][sg!=0]) < .001):
                raise RuntimeError('Phonon spin branch collapsed')
            f = np.asarray(model.efs(a, spin['moments'])['forces'])
        forces.append(f-f.mean(axis=0))
    p.forces=forces;p.produce_force_constants();p.symmetrize_force_constants()
    result = dict(symmetry_reduced=np.asarray(symmetry_reduced),
                  displacement_count=np.asarray(len(forces)))
    for kind in ['mesh','band']:
        q=sampling[kind+'_qpoints'];p.run_qpoints(q)
        result[kind+'_qpoints']=q;result[kind+'_frequencies_THz']=p.qpoints.frequencies
    return result

def head_exchange(model,definition,cfg,volume_delta=0.,relaxed=None):
    a = atoms_from(definition['unitcell']) if relaxed is None else relaxed.copy()
    if a.get_chemical_symbols() != definition['unitcell']['species']:
        raise ValueError('Exchange input ordering differs from the relaxed cell')
    a.set_cell(a.cell*(1+volume_delta)**(1/3),scale_atoms=True)
    signs=np.asarray(definition['magnetic_signs'],float)
    if relaxed is not None:
        moments = a.get_initial_magnetic_moments()
        signs = np.sign(moments)
    elif getattr(model, 'moment_predictor', None) is not None:
        moments = model.initial_moments(a, signs*cfg['amplitude'], signs)
        moments = np.clip(moments, -cfg['moment_bound'], cfg['moment_bound'])
    else:
        spin = optimize_moments(model, a, signs*cfg['amplitude'], cfg, signs=signs)
        if not spin['converged']:
            raise RuntimeError('Exchange-head reference branch did not converge')
        moments = spin['moments']
    if relaxed is None and np.any(abs(moments[signs!=0]) < .001):
        raise RuntimeError('Exchange-head branch collapsed')
    values = model.exchange_bonds(a, moments, definition['periodic_bonds'])
    labels=np.array([b[3] for b in definition['periodic_bonds']]);nj=len(definition['parameters'])
    if set(labels)!=set(range(nj)):raise ValueError('Incomplete exchange parameter coverage')
    return np.array([values[labels==k].mean() for k in range(nj)])

def head_volume_exchange(model,definition,cfg,deltas=(-.01,-.005,.005,.01),relaxed=None):
    j0=head_exchange(model,definition,cfg,relaxed=relaxed);x=np.log1p(deltas)
    values=np.array([head_exchange(model,definition,cfg,d,relaxed=relaxed)-j0 for d in deltas])
    return np.linalg.lstsq(np.stack([x,x*x],axis=1),values,rcond=None)[0][0]
