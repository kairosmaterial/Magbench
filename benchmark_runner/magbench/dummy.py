"""Analytic, nonphysical adapter for interface tests; never a benchmark model."""
import numpy as np


class DummyAdapter:
    def __init__(self, checkpoint, device='cpu', head_checkpoint=None):
        self.moment_predictor = None

    def initial_moments(self, atoms, seeds, signs=None):
        return np.asarray(seeds, dtype=float)

    def energy(self, atoms, moments):
        return float(np.sum(np.asarray(moments) ** 2) / 2)

    def energy_gradient(self, atoms, moments):
        return self.energy(atoms, moments), np.asarray(moments, dtype=float)

    def efs(self, atoms, moments):
        return dict(energy=self.energy(atoms, moments),
                    forces=np.zeros((len(atoms), 3)), stress=np.zeros(6))

    def supports_exchange_head(self):
        return False
