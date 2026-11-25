"""Collinear moment prediction from signed seeds."""
import hashlib

import numpy as np
import torch
from ase.calculators.calculator import Calculator, all_changes
from ase.data import atomic_numbers
from ase.stress import full_3x3_to_voigt_6_stress

from .adapter import read_checkpoint
from .graph import Batch, Collator, sample_from_atoms
from .heads import MagmomHead, MagmomHeadX, features, features_ex
from .runtime import SpinRuntime


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_head_binding(model_path, config):
    """Reject a new head bound to different energy-file bytes before loading them."""
    expected = config.get('energy_sha256')
    if expected is None:
        return
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('Invalid energy checkpoint SHA256 in head header')
    if file_sha256(model_path) != expected:
        raise ValueError('This head belongs to a different energy checkpoint')


def seed_table(config, device='cpu'):
    table = torch.full((119, 3), .1)
    for symbol, levels in config.get('seed_levels', {}).items():
        z = atomic_numbers[symbol]
        table[z] = torch.tensor(levels)
    return table.to(device)


class MagmomPredictor(Calculator):
    implemented_properties = ['energy', 'free_energy', 'forces', 'stress', 'magmoms']

    def __init__(self, model_path, head_path, device='cuda', seed_mode='lut',
                 magnetic_threshold=.5, use_kernel=None, **kwargs):
        super().__init__(**kwargs)
        if seed_mode not in ('lut', 'raw'):
            raise ValueError("seed_mode must be 'lut' or 'raw'")
        self.seed_mode = seed_mode
        self.magnetic_threshold = float(magnetic_threshold)
        config, payload = read_checkpoint(head_path)
        if config.get('kind', 'head') != 'head':
            raise ValueError('A moment-head checkpoint is required')
        validate_head_binding(model_path, config)
        self.runtime = SpinRuntime(model_path, device=device, use_kernel=use_kernel)
        self.dev = self.runtime.dev
        if config.get('energy_sha256'):
            self.backbone = self.runtime.model
        elif 'backbone' in payload:
            # Published bundles carry their own backbone; require the supplied pair to match.
            reference = self.runtime.model.state_dict()
            for k, v in payload['backbone'].items():
                if k == 'model.exchange.branch_scales' and k not in reference and torch.equal(v, torch.ones(1)):
                    continue
                if '.tp.' not in k and (k not in reference or not torch.equal(v, reference[k].cpu())):
                    raise ValueError('Published head backbone differs from the supplied energy model')
            self.backbone = self.runtime.model
        else:
            raise ValueError('Head checkpoint has no energy-model identity')
        self.head = (MagmomHeadX(e_max=float(config.get('e_max', 1.)))
                     if config.get('headx') else MagmomHead())
        self.head.load_state_dict(payload['head'], strict=True)
        self.head.to(self.dev).eval().requires_grad_(False)
        self.config = config
        self.lut = seed_table(config, self.dev)
        self.collator = Collator(self.backbone.graph_cutoff)

    def seed_amplitudes(self, atoms, level=1):
        """Per-element positive amplitudes in muB; levels are 0, 1 or 2."""
        if level not in (0, 1, 2):
            raise ValueError('level must be 0, 1 or 2')
        self.runtime.validate(atoms)
        return self.lut[torch.as_tensor(atoms.numbers, device=self.dev), level].cpu().numpy()

    def prepare_seeds(self, atoms, seeds):
        seeds = np.asarray(seeds, dtype=float)
        if seeds.shape != (len(atoms),) or not np.isfinite(seeds).all():
            raise ValueError('Seeds must be a finite collinear (N,) array')
        if self.seed_mode == 'raw':
            return seeds
        return np.where(abs(seeds) > self.magnetic_threshold,
                        np.sign(seeds) * self.seed_amplitudes(atoms), 0.).astype(np.float32)

    @torch.no_grad()
    def predict_moments(self, atoms, seeds):
        self.runtime.validate(atoms)
        m0 = self.prepare_seeds(atoms, seeds)
        batch = Batch(self.collator([sample_from_atoms(atoms, m0)])).to(self.dev)
        if isinstance(self.head, MagmomHeadX):
            h, e = features_ex(self.backbone, batch, batch.magmoms)
            predicted = self.head(batch.magmoms, h, e)
        else:
            predicted = self.head(batch.magmoms, features(self.backbone, batch, batch.magmoms))
        return predicted.cpu().numpy()

    def calculate(self, atoms=None, properties=None, system_changes=all_changes):
        Calculator.calculate(self, atoms)
        moments = self.predict_moments(atoms, atoms.get_initial_magnetic_moments())
        out = self.runtime.efs(atoms, moments)
        self.results = dict(magmoms=moments, energy=out['energy'], free_energy=out['energy'],
                            forces=out['forces'], stress=full_3x3_to_voigt_6_stress(out['stress_3x3']))
