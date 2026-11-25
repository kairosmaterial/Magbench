"""MagBench adapter using the Prophet-Spin inference package."""
import numpy as np


class ProphetSpinV1:
    def __init__(self, checkpoint, device='cuda', head_checkpoint=None, use_kernel=None):
        from prophet_spin import MagmomPredictor, SpinRuntime
        self.moment_predictor = None
        if head_checkpoint is None:
            self.runtime = SpinRuntime(checkpoint, device=device, use_kernel=use_kernel)
        else:
            # The two full-data entries use the model seed table. The small entries
            # retain the runner's uniform seeds without amplitude preprocessing.
            self.moment_predictor = MagmomPredictor(checkpoint, head_checkpoint,
                                                    device=device, seed_mode='raw', use_kernel=use_kernel)
            if self.moment_predictor.runtime.config.get('backbone') == 'full':
                self.moment_predictor.seed_mode = 'lut'
            self.runtime = self.moment_predictor.runtime
        self.elements = set(self.runtime.atomic_numbers)

    def initial_moments(self, atoms, seeds, signs=None):
        if self.moment_predictor is None:
            return np.asarray(seeds, dtype=float)
        moments = self.moment_predictor.predict_moments(atoms, seeds)
        if signs is not None:
            moments = np.asarray(signs) * np.maximum(abs(moments), .1)
        return moments

    def validate(self, atoms):
        return self.runtime.validate(atoms)

    def energy(self, atoms, moments):
        return self.runtime.energy(atoms, moments)

    def prepare_energy_gradient(self, atoms):
        return self.runtime.prepare_energy_gradient(atoms)

    def energy_gradient(self, atoms, moments):
        return self.runtime.energy_gradient(atoms, moments)

    def joint_efs(self, atoms, moments):
        return self.runtime.joint_efs(atoms, moments)

    def efs(self, atoms, moments):
        result = self.runtime.efs(atoms, moments)
        return dict(energy=result['energy'], forces=result['forces'], stress=result['stress_voigt'])

    def supports_exchange_head(self):
        return self.runtime.supports_exchange_head()

    def exchange_bonds(self, atoms, moments, bonds):
        return self.runtime.exchange_bonds(atoms, moments, bonds)


