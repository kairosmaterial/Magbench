import numpy as np
import torch

from .adapter import load_spin_model
from .backbone import MagmomGraft, polynomial_cutoff
from .graph import Batch, Collator, sample_from_atoms


class PairHamiltonian:
    def __init__(self, e0, pairs_i, pairs_j, exchange, r, natoms):
        self.e0 = float(e0)
        self.pairs_i, self.pairs_j, self.exchange, self.r = pairs_i, pairs_j, exchange, r
        self.natoms = int(natoms)
        tmp = [[] for _ in range(self.natoms)]
        for k, (a, b) in enumerate(zip(pairs_i, pairs_j)):
            tmp[a].append((int(b), float(exchange[k])))
            tmp[b].append((int(a), float(exchange[k])))
        self.nbr_idx = [np.array([x[0] for x in t], dtype=np.int64) for t in tmp]
        self.nbr_exchange = [np.array([x[1] for x in t]) for t in tmp]

    def energy(self, spins):
        spins = np.asarray(spins, dtype=float)
        if spins.ndim == 1:
            dots = spins[self.pairs_i] * spins[self.pairs_j]
        else:
            dots = (spins[self.pairs_i] * spins[self.pairs_j]).sum(-1)
        return self.e0 + float((self.exchange * dots).sum())

    def delta_single(self, spins, site, new_spin):
        spins = np.asarray(spins, dtype=float)
        idx, ex = self.nbr_idx[site], self.nbr_exchange[site]
        if not len(idx):
            return 0.0
        d = np.asarray(new_spin, dtype=float) - spins[site]
        if spins.ndim == 1:
            return float((ex * (d * spins[idx])).sum())
        return float((ex * (spins[idx] @ d)).sum())

    def save(self, path):
        np.savez_compressed(
            path, e0=self.e0, pairs_i=self.pairs_i, pairs_j=self.pairs_j,
            J=self.exchange, r=self.r, natoms=self.natoms,
        )

    @classmethod
    def load(cls, path):
        z = np.load(path)
        return cls(float(z["e0"]), z["pairs_i"], z["pairs_j"], z["J"], z["r"],
                   int(z["natoms"]))


class SpinRuntime:
    def __init__(self, model_path: str, device: str = "cuda", use_kernel=None):
        self.dev = torch.device(device)
        self.model, self.config = load_spin_model(model_path, device=self.dev, use_kernel=use_kernel)
        self.model = self.model.to(self.dev)
        self.collator = Collator(cutoff=self.model.graph_cutoff)
        self.atomic_numbers = tuple(self.config["atomic_numbers"])

    def _sample(self, atoms, moments):
        self.validate(atoms)
        return sample_from_atoms(atoms, moments)

    def validate(self, atoms):
        if not len(atoms):
            raise ValueError("Empty structures are not supported")
        missing = set(map(int, atoms.numbers)) - set(self.atomic_numbers)
        if missing:
            raise ValueError(f"Unsupported atomic numbers: {sorted(missing)}")
        if not np.all(atoms.pbc) or abs(np.linalg.det(atoms.cell)) < 1e-8:
            raise ValueError("Use a fully periodic structure with a nonsingular cell")

    def _batch(self, samples):
        return Batch(self.collator(samples)).to(self.dev)

    @torch.no_grad()
    def energy(self, atoms, magmoms) -> float:
        b = self._batch([self._sample(atoms, magmoms)])
        return float(self.model.forward_energy(b).item())

    @torch.no_grad()
    def energies_batch(self, atoms, magmoms_list, batch_size: int = 64):
        out = []
        for k in range(0, len(magmoms_list), batch_size):
            chunk = magmoms_list[k:k + batch_size]
            b = self._batch([self._sample(atoms, m) for m in chunk])
            out.append(self.model.forward_energy(b).detach().cpu().numpy())
        return np.concatenate(out)

    @torch.no_grad()
    def efs(self, atoms, magmoms):
        b = self._batch([self._sample(atoms, magmoms)])
        out = self.model(b)
        s3 = out["stress"].detach().cpu().numpy().reshape(3, 3)
        voigt = np.array([s3[0, 0], s3[1, 1], s3[2, 2], s3[1, 2], s3[0, 2], s3[0, 1]])
        return {
            "energy": float(out["energy"].item()),
            "energy_per_atom": float(out["energy"].item()) / len(atoms),
            "forces": out["forces"].detach().cpu().numpy(),
            "stress_voigt": voigt,
            "stress_3x3": s3,
        }

    def _atoms_batch(self, atoms, moments):
        return self._batch([self._sample(atoms, moments)])

    def supports_exchange_head(self):
        return self.model.model.exchange is not None

    def prepare_energy_gradient(self, atoms):
        rt, t = (self, torch)
        b = self._atoms_batch(atoms, np.zeros(len(atoms)))
        species, edges, shifts, idx, n = rt.model._common_inputs(b)
    
        def call(moments):
            with t.enable_grad():
                m = t.as_tensor(np.array(moments, copy=True), dtype=b.pos.dtype, device=rt.dev).requires_grad_(True)
                node, _ = rt.model.model.forward_features(species, b.pos, shifts, edges, b.cell, idx, magmoms=m)
                energy = rt.model._energy_per_graph(node, idx, n).sum()
                g, = t.autograd.grad(energy, m, materialize_grads=True)
            return (float(energy.detach().cpu()), g.detach().cpu().numpy())
        return call

    def energy_gradient(self, atoms, moments):
        return self.prepare_energy_gradient(atoms)(moments)

    def joint_efs(self, atoms, moments):
        from ase.stress import full_3x3_to_voigt_6_stress
        rt, t = (self, torch)
        b = self._atoms_batch(atoms, moments)
        species, edges, shifts, idx, n = rt.model._common_inputs(b)
        with t.enable_grad():
            pos = b.pos.detach().requires_grad_(True)
            m = b.magmoms.detach().requires_grad_(True)
            strain = t.zeros_like(b.cell, requires_grad=True)
            s = (strain + strain.transpose(-1, -2)) / 2
            node, _ = rt.model.model.forward_features(species, pos + pos @ s[0], shifts, edges, b.cell + b.cell @ s, idx, magmoms=m)
            energy = rt.model._energy_per_graph(node, idx, n).sum()
            pg, sg, mg = t.autograd.grad(energy, (pos, strain, m), materialize_grads=True)
            stress = sg[0] / abs(t.linalg.det(b.cell[0]))
        result = dict(energy=float(energy.detach().cpu()), forces=-pg.detach().cpu().numpy(), stress=full_3x3_to_voigt_6_stress(stress.detach().cpu().numpy()), moment_gradient=mg.detach().cpu().numpy().reshape(len(atoms)))
        return result

    @staticmethod
    def _periodic_pair(i, j, shift):
        s = tuple(map(int, shift))
        return min((int(i), int(j), *s), (int(j), int(i), *(-v for v in s)))

    def _hd_pair_coefficients(self, atoms, moments):
        """All unordered periodic coefficients K in E=sum K*m_i*m_j+constant.
    
      At fixed magnitudes the structural trunk, density weights and coefficients
      are independent of signs. Each shared centre contributes
      2*sum_a w_ja*w_ka*(c_a+e_a*rhat_j.rhat_k); its centre-neighbour
      contribution is sum_a d_a*w_ja. Coincident-site terms are constant.
      """
        from .backbone import polynomial_cutoff
        rt, t = (self, torch)
        model = rt.model.model
        ex = model.exchange
        dens = model.heisenberg_density
        capture = {}
    
        def hook(name):
    
            def take(module, args, out):
                capture[name] = (args, out)
            return take
        handles = [ex.register_forward_hook(hook('direct')), ex.mlp.register_forward_hook(hook('j')), dens.register_forward_hook(hook('density')), dens.weight_mlp.register_forward_hook(hook('w')), dens.coefficient_mlp.register_forward_hook(hook('coeff'))]
        try:
            with t.no_grad():
                b = self._atoms_batch(atoms, moments)
                energy = rt.model.forward_energy(b)
                _, edges, shifts, _, _ = rt.model._common_inputs(b)
                _, mm, dist, send, recv, _ = capture['direct'][0][:6]
                mask = dist < ex.r_max
                directed = 0.5 * capture['j'][1].squeeze(-1) * (ex.branch_scales[0] if hasattr(ex, 'branch_scales') else 1.) * polynomial_cutoff(dist[mask], ex.r_max)
                hd, md, dr, sd, rd = capture['density'][0]
                distance = dr.norm(dim=-1)
                active = distance < dens.r_max
                d = distance[active]
                x = d / dens.r_max
                env = 1.0 - 28.0 * x.pow(6) + 48.0 * x.pow(7) - 21.0 * x.pow(8)
                w = (capture['w'][1] * env.unsqueeze(-1)).double().cpu().numpy()
                coeff = capture['coeff'][1].double().cpu().numpy()
                rhat = (dr[active] / d.clamp_min(1e-08).unsqueeze(-1)).double().cpu().numpy()
                assert t.equal(sd, edges[0]) and t.equal(rd, edges[1])
                si = sd[active].cpu().numpy()
                ri = rd[active].cpu().numpy()
                image = np.rint(shifts[active].cpu().numpy()).astype(int)
                de = edges[:, mask].cpu().numpy()
                ds = np.rint(shifts[mask].cpu().numpy()).astype(int)
                dv = directed.double().cpu().numpy()
                self.last_pair_audit = dict(energy_eV=float(energy.cpu()), direct_energy_eV=float(capture['direct'][1].double().sum().cpu()), density_energy_eV=float(capture['density'][1].double().sum().cpu()), density_radius_A=dens.r_max, direct_radius_A=ex.r_max)
        finally:
            for handle in handles:
                handle.remove()
        pairs = {}
    
        def add(i, j, s, v):
            key = self._periodic_pair(i, j, s)
            if key[0] == key[1] and key[2:] == (0, 0, 0):
                return
            pairs[key] = pairs.get(key, 0.0) + float(v)
        for i, j, s, v in zip(de[1], de[0], ds, dv):
            add(i, j, s, v)
        mediated = []
        magnitudes = np.abs(np.asarray(moments, float))
        for centre in np.unique(ri):
            loc = np.flatnonzero(ri == centre)
            wc = w[loc]
            c, dc, e = np.split(coeff[centre], 3)
            for a, v in zip(loc, wc @ dc):
                add(centre, si[a], image[a], v)
            a, z = np.triu_indices(len(loc), 1)
            values = 2.0 * (wc * c @ wc.T + rhat[loc] @ rhat[loc].T * (wc * e @ wc.T))
            magnetic = (magnitudes[si[loc[a]]] >= 0.5) & (magnitudes[si[loc[z]]] >= 0.5)
            if magnitudes[centre] < 0.5 and magnetic.any():
                mediated.append(dict(centre=int(centre), species=atoms[centre].symbol, max_abs_K_eV_muB2=float(np.max(abs(values[a[magnetic], z[magnetic]])))))
            for u, v, value in zip(loc[a], loc[z], values[a, z]):
                add(si[u], si[v], image[v] - image[u], value)
        self.last_pair_audit['nonmagnetic_centre_mediation'] = mediated
        return pairs

    def exchange_bonds(self, atoms, moments, bonds):
        if not self.supports_exchange_head():
            raise ValueError('Checkpoint has no supported exchange readout')
        self.validate(atoms)
        moments = np.asarray(moments, dtype=float)
        if moments.shape != (len(atoms),) or not np.isfinite(moments).all():
            raise ValueError('Exchange readout requires finite collinear moments')
        if getattr(self.model.model, 'heisenberg_density', None) is not None:
            from ase.neighborlist import neighbor_list
            pairs = self._hd_pair_coefficients(atoms, moments)
            m = np.abs(np.asarray(moments, float))
            result = []
            zeros = []
            direct_radius = self.model.model.exchange.r_max
            density_radius = self.model.model.heisenberg_density.r_max
            missing = [b for b in bonds if self._periodic_pair(*b[:3]) not in pairs]
            if missing:
                centre_i, centre_j, centre_s = neighbor_list('ijS', atoms, density_radius)
            for i, j, s, label in bonds:
                key = self._periodic_pair(i, j, s)
                if key not in pairs:
                    p = atoms.positions[i]
                    q = atoms.positions[j] + np.asarray(s) @ atoms.cell
                    distance = float(np.linalg.norm(q - p))
                    centres = atoms.positions[centre_j[centre_i == i]] + centre_s[centre_i == i] @ atoms.cell
                    shared = bool(np.any(np.linalg.norm(centres - q, axis=1) < density_radius))
                    if distance < direct_radius or shared:
                        raise ValueError('Missing supported periodic HD pair')
                    zeros.append(dict(i=int(i), j=int(j), shift=list(map(int, s)), label=int(label), distance_A=distance))
                result.append(1000.0 * pairs.get(key, 0.0) * m[i] * m[j])
            return np.asarray(result)
        from .backbone import MagmomGraft, polynomial_cutoff
        rt, t = (self, torch)
        capture = {}
        ex = rt.model.model.exchange
        handle = ex.register_forward_hook(lambda module, args, out: capture.update(args=args))
        try:
            with t.no_grad():
                b = self._atoms_batch(atoms, moments)
                rt.model.forward_energy(b)
                _, edges, shifts, _, _ = rt.model._common_inputs(b)
                h, mm, dist, send, recv, _ = capture['args'][:6]
                assert t.equal(send, edges[0]) and t.equal(recv, edges[1])
                q = mm[send] ** 2 + mm[recv] ** 2
                feat = t.cat([h[send] + h[recv], MagmomGraft._basis(dist, getattr(ex, 'r_centers_0', getattr(ex, 'r_centers', None)), ex.r_widths[0] if hasattr(ex, 'r_widths') else ex.r_width), MagmomGraft._basis(q, ex.q_centers, ex.q_width)], dim=-1)
                directed = 0.5 * ex.mlp(feat).squeeze(-1) * (ex.branch_scales[0] if hasattr(ex, 'branch_scales') else 1.) * polynomial_cutoff(dist, ex.r_max)
                values = (1000 * directed * abs(mm[send] * mm[recv])).cpu().numpy()
                edges = edges.cpu().numpy()
                shifts = np.rint(shifts.cpu().numpy()).astype(int)
        finally:
            handle.remove()
    
        def canonical(i, j, s):
            return min((int(i), int(j), *map(int, s)), (int(j), int(i), *map(int, -np.asarray(s))))
        agg = {}
        for i, j, s, v in zip(edges[1], edges[0], shifts, values):
            key = canonical(i, j, s)
            agg[key] = agg.get(key, 0.0) + float(v)
        result = []
        for i, j, s, _ in bonds:
            k = canonical(i, j, s)
            if k not in agg and np.linalg.norm(atoms.positions[j] + np.asarray(s) @ atoms.cell - atoms.positions[i]) < rt.model.graph_cutoff - 1e-05:
                raise ValueError('Missing in-cutoff periodic bond')
            result.append(agg.get(k, 0.0))
        return np.asarray(result)

    def extract_pair_hamiltonian(self, atoms, magmoms):
        from ase.neighborlist import neighbor_list
        i, j, shifts, distances = neighbor_list('ijSd', atoms, 2 * self.model.graph_cutoff)
        keys = sorted({self._periodic_pair(a, b, s) for a, b, s in zip(i, j, shifts)
                       if a != b})
        bonds = [(a, b, key_shift, 0) for a, b, *key_shift in keys]
        values = self.exchange_bonds(atoms, magmoms, bonds)
        m = np.abs(np.asarray(magmoms, dtype=float))
        if m.ndim != 1:
            raise ValueError('Pair extraction requires collinear moments')
        aggregate = {}
        for key, value in zip(keys, values):
            a, b = key[:2]
            if m[a] * m[b] != 0:
                pair = tuple(sorted((a, b)))
                aggregate[pair] = aggregate.get(pair, 0.) + value / (1000. * m[a] * m[b])
        pairs = sorted(aggregate)
        ii = np.array([k[0] for k in pairs], dtype=int)
        jj = np.array([k[1] for k in pairs], dtype=int)
        coupling = np.array([aggregate[k] for k in pairs])
        reference = self.energy(atoms, magmoms)
        e0 = reference - float(np.sum(coupling * np.asarray(magmoms)[ii] * np.asarray(magmoms)[jj]))
        nearest = {}
        for a, b, distance in zip(i, j, distances):
            pair = tuple(sorted((int(a), int(b))))
            nearest[pair] = min(nearest.get(pair, np.inf), float(distance))
        return PairHamiltonian(e0, ii, jj, coupling, np.array([nearest[k] for k in pairs]), len(atoms))
