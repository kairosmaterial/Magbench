"""Checkpoint configuration and tensor-only loading."""
import importlib.util
import io
import json
import pickle

import torch
from torch import nn

ARCH_KEYS = (
    'lmax', 'hidden_irreps', 'n_layers', 'radial_basis_size', 'radial_mlp_size',
    'radial_mlp_layers', 'radial_polynomial_p', 'mlp_init_scale', 'index_weights',
    'layer_norm', 'kernel', 'shift', 'scale', 'avg_n_neighbors', 'cutoffs', 'model_name',
)


def resolve_kernel(config, device='cpu', use_kernel=None):
    cuda = torch.device(device).type == 'cuda'
    if use_kernel is None:
        use_kernel = cuda and importlib.util.find_spec('openequivariance') is not None
    if use_kernel and not cuda:
        raise ValueError('use_kernel=True requires a CUDA device')
    return dict(config, kernel=bool(use_kernel))


def read_checkpoint(path):
    """Read a bounded JSON header followed by a tensor-only checkpoint."""
    try:
        with open(path, 'rb') as stream:
            line = stream.readline(65537)
            if len(line) > 65536 or not line.endswith(b'\n'):
                raise ValueError('Checkpoint requires a JSON header line of at most 65536 bytes')
            config = json.loads(line)
            if not isinstance(config, dict):
                raise ValueError('Checkpoint header must be a JSON object')
            if type(config.get('format_version', 1)) is not int or config.get('format_version', 1) != 1:
                raise ValueError('Unsupported checkpoint format version')
            if config.get('kind', 'energy') not in ('energy', 'head'):
                raise ValueError('Unsupported checkpoint kind')
            payload = torch.load(io.BytesIO(stream.read()), map_location='cpu', weights_only=True)
    except (UnicodeError, json.JSONDecodeError, EOFError, RuntimeError, IndexError, KeyError, pickle.UnpicklingError) as exc:
        raise ValueError('Malformed checkpoint header or tensor payload') from exc
    if not isinstance(payload, dict) or not all(isinstance(k, str) for k in payload):
        raise ValueError('Checkpoint payload must be a state dictionary')
    states = payload.values() if 'head' not in payload else [v for state in payload.values()
              for v in (state.values() if isinstance(state, dict) else [state])]
    if not all(torch.is_tensor(v) for v in states):
        raise ValueError('Checkpoint payload must contain only tensors')
    return config, payload


def load_state(model, state):
    """Only deterministic tensor-product constants may be absent or regenerated."""
    state = {k: v for k, v in state.items() if '.tp.' not in k}
    generated = model.state_dict()
    legacy_scale = 'model.exchange.branch_scales'
    if legacy_scale in state and legacy_scale not in generated:
        if model.config.get('backbone', 'legacy') != 'legacy' or not torch.equal(state[legacy_scale], torch.ones(1)):
            raise ValueError('Unsupported legacy exchange scale')
        state.pop(legacy_scale)
    parameters = dict(model.named_parameters())
    extra = set(state) - set(generated)
    missing = [k for k in generated if k not in state and k != 'z2idx' and
               ('.tp.' not in k or (k in parameters and parameters[k].numel()))]
    if extra or missing:
        raise ValueError(f'Checkpoint mismatch: extra={sorted(extra)}, missing={missing}')
    for k, value in state.items():
        if not torch.is_tensor(value) or value.shape != generated[k].shape or value.dtype != generated[k].dtype:
            raise ValueError(f'Checkpoint tensor shape or dtype mismatch: {k}')
    model.load_state_dict({**generated, **state}, strict=True)


class ProphetSpin(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        family = config.get('backbone', 'lora' if config.get('lora_rank', 0) else 'legacy')
        from .backbone import SpinBackbone
        if family not in ('full', 'lora', 'legacy'):
            raise ValueError(f'Unsupported backbone: {family}')
        extra_keys = ('lora_rank', 'lora_gate_hops', 'token_gate', 'lora_gate_m0',
                      'heisenberg_density', 'heisenberg_density_radius',
                      'heisenberg_density_channels', 'heisenberg_density_hidden')
        self.model = SpinBackbone(
            n_species=len(config['atomic_numbers']), cutoff=float(max(config['cutoffs'])),
            magmom_conditioning=bool(config.get('magmom_conditioning', True)),
            heisenberg_mode=bool(config.get('heisenberg_mode', True)),
            exchange_r_max=config.get('exchange_r_max'),
            radial_basis=config.get('radial_basis', 'gaussian' if family == 'lora' else 'bessel'),
            exchange_layout=config.get('exchange_layout', 'branched' if family == 'full' else 'compact'),
            exchange_learnable_scale=config.get('exchange_learnable_scale', family != 'legacy'),
            **{k: config[k] for k in ARCH_KEYS},
            **{k: config[k] for k in extra_keys if k in config},
        )
        zmap = torch.zeros(119, dtype=torch.long)
        for i, z in enumerate(config['atomic_numbers']):
            zmap[int(z)] = i
        self.register_buffer('z2idx', zmap)

    def _common_inputs(self, data):
        species = self.z2idx[data.atomic_numbers.long()]
        edge_index = data.edge_index.flip(0)
        shifts = data.cell_offsets
        idx = data.batch
        n = int(idx.max().item()) + 1 if idx.numel() else 1
        return species, edge_index, shifts, idx, n

    def _energy_per_graph(self, node, idx, n):
        node = node.squeeze(-1) if node.dim() > 1 else node
        return node.new_zeros(n).scatter_add(0, idx, node)

    @property
    def graph_cutoff(self):
        exchange = self.model.exchange
        return max(float(self.model.cutoff), float(exchange.r_max) if exchange is not None else 0.)

    @torch.no_grad()
    def forward_energy(self, data):
        species, edges, shifts, idx, n = self._common_inputs(data)
        node, _ = self.model.forward_features(species, data.pos, shifts, edges,
                                              data.cell, idx, magmoms=data.magmoms)
        return self._energy_per_graph(node, idx, n)

    def forward(self, data):
        species, edges, shifts, idx, n = self._common_inputs(data)
        with torch.enable_grad():
            pos = data.pos.detach().requires_grad_(True)
            node, force, stress = self.model(species, pos, shifts, edges, data.cell,
                                             data.natoms, None, idx, magmoms=data.magmoms)
        return dict(energy=self._energy_per_graph(node, idx, n), forces=force, stress=stress)


def load_model(path, device='cpu', use_kernel=None):
    """Return (model, configuration), in evaluation mode on the requested device."""
    config, state = read_checkpoint(path)
    if config.get('kind', 'energy') != 'energy':
        raise ValueError('An energy checkpoint is required')
    config = resolve_kernel(config, device, use_kernel)
    model = ProphetSpin(config)
    load_state(model, state)
    for i, z in enumerate(config['atomic_numbers']):
        if model.z2idx[z].item() != i:
            raise ValueError('Checkpoint atomic-number mapping mismatch')
    return model.to(device).eval().requires_grad_(False), config


load_spin_model = load_model
