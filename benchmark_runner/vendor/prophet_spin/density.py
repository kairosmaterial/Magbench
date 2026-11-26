from __future__ import annotations
import torch
from torch import nn

def _sum_nodes(values: torch.Tensor, receivers: torch.Tensor, n: int) -> torch.Tensor:
    return values.new_zeros((n,) + values.shape[1:]).index_add(0, receivers, values)

class HeisenbergDensityReadout(nn.Module):

    def __init__(self, scalar_dim: int, r_max: float=3.0, channels: int=8, hidden: int=128, r_basis: int=16, mag_basis: int=12, m2_max: float=32.0):
        super().__init__()
        if r_max <= 0 or channels < 1 or r_basis < 2 or (mag_basis < 2):
            raise ValueError('Positive radius/channels and at least two basis functions required')
        self.r_max = float(r_max)
        self.channels = int(channels)
        self.register_buffer('r_centers', torch.linspace(0.0, self.r_max, r_basis))
        self.register_buffer('m2_centers', torch.linspace(0.0, m2_max, mag_basis))
        self.r_width = 1.5 * self.r_max / (r_basis - 1)
        self.m2_width = 1.5 * m2_max / (mag_basis - 1)
        self.weight_mlp = nn.Sequential(nn.Linear(scalar_dim + r_basis, hidden), nn.SiLU(), nn.Linear(hidden, self.channels))
        self.coefficient_mlp = nn.Sequential(nn.Linear(scalar_dim + mag_basis, hidden), nn.SiLU(), nn.Linear(hidden, hidden), nn.SiLU(), nn.Linear(hidden, 3 * self.channels))
        nn.init.zeros_(self.coefficient_mlp[-1].weight)
        nn.init.zeros_(self.coefficient_mlp[-1].bias)

    @staticmethod
    def _vectors(m: torch.Tensor) -> torch.Tensor:
        if m.ndim == 1:
            return torch.stack((m, torch.zeros_like(m), torch.zeros_like(m)), -1)
        if m.ndim == 2 and m.shape[-1] == 3:
            return m
        raise ValueError('magmoms must have shape [N] or [N,3]')

    def forward(self, h: torch.Tensor, magmoms: torch.Tensor, displacements: torch.Tensor, senders: torch.Tensor, receivers: torch.Tensor) -> torch.Tensor:
        if displacements.ndim != 2 or displacements.shape[-1] != 3:
            raise ValueError('Density tensors require full [E,3] periodic displacements')
        if h.shape[0] != magmoms.shape[0] or displacements.shape[0] != senders.numel():
            raise ValueError('Inconsistent node or edge counts')
        dtype = torch.float64 if h.dtype == torch.float64 else torch.float32
        m = self._vectors(magmoms).to(dtype)
        distances = displacements.norm(dim=-1)
        active = distances < self.r_max
        s, r = (senders[active], receivers[active])
        d = distances[active]
        dr = displacements[active]
        rb = torch.exp(-((d.unsqueeze(-1) - self.r_centers) / self.r_width).square())
        x = d / self.r_max
        env = 1.0 - 28.0 * x.pow(6) + 48.0 * x.pow(7) - 21.0 * x.pow(8)
        w = self.weight_mlp(torch.cat((h[s], rb.to(h.dtype)), -1)).to(dtype)
        w = w * env.to(dtype).unsqueeze(-1)
        weighted_m = w.unsqueeze(-1) * m[s].unsqueeze(1)
        v = _sum_nodes(weighted_m, r, len(h))
        rhat = (dr / d.clamp_min(1e-08).unsqueeze(-1)).to(dtype)
        t = _sum_nodes(rhat[:, None, :, None] * weighted_m[:, :, None, :], r, len(h))
        quadratic = torch.cat((v.square().sum(-1), (m.unsqueeze(1) * v).sum(-1), t.square().sum((-1, -2))), -1)
        m2 = m.square().sum(-1)
        m2b = torch.exp(-((m2.unsqueeze(-1) - self.m2_centers) / self.m2_width).square())
        coeff = self.coefficient_mlp(torch.cat((h, (m2.unsqueeze(-1) * m2b).to(h.dtype)), -1))
        return (coeff.to(dtype) * quadratic).sum(-1)
