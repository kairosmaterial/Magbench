"""Trusted selection of converged model candidates after the ground-state phase."""
from pathlib import Path

from .cli import load
from .scoring import GROUND_STATE_TOLERANCE_MEV_ATOM, MAX_RELATIVE_MOMENT_ERROR, select_ground_candidate


def selection_receipt(reference, expected, outputs):
    reference = Path(reference)
    targets = load(reference / 'ground_state.json')
    natoms = {key: case['natoms'] for key, case in load(reference / 'hull.json').items()}
    expected = set(expected)
    converged = set()
    failures = set()
    selected = {}
    dft_moments = {}
    for output in map(Path, outputs):
        for path in (output / 'completed').glob('*/ground_state.json'):
            key = path.parent.name
            if key not in expected or key in converged:
                raise ValueError(f'Unexpected or duplicate ground-state result for {key}')
            converged.add(key)
            candidate, _ = select_ground_candidate(load(path), targets[key], natoms[key])
            if candidate is not None:
                selected[key] = candidate['seed_index']
                dft_moments[key] = targets[key]['reference_magmoms_muB']
        errors = output / 'errors.json'
        if errors.exists():
            failures.update(k.split('/')[0] for k in load(errors) if k.endswith('/ground_state'))
    missing = expected - converged - failures
    if missing:
        raise ValueError(f'Ground-state phase incomplete for {sorted(missing)}')
    return dict(terminal_materials=sorted(expected), converged=sorted(converged),
                failed=sorted((failures & expected) - converged),
                tolerance_meV_atom=GROUND_STATE_TOLERANCE_MEV_ATOM,
                max_relative_moment_error=MAX_RELATIVE_MOMENT_ERROR,
                selected_seed_indices=selected, dft_moments_muB=dft_moments)
