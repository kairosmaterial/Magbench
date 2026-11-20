"""Trusted model adapters. Energies eV/cell, forces eV/Å, stress eV/Å³."""
import numpy as np

class ProphetSpinV2:
    def __init__(self, checkpoint, device='cuda', head_checkpoint=None):
        import torch
        from prophet_spin import SpinRuntime
        self.torch=torch
        self.runtime=SpinRuntime(str(checkpoint),device=device)
        self.runtime.model.eval()
        for p in self.runtime.model.parameters(): p.requires_grad_(False)
        self.elements=set(self.runtime.model.config['atomic_numbers'])
        self.moment_predictor=None
        if head_checkpoint is not None:
            from prophet_spin.predictor import MagmomPredictor
            self.moment_predictor=MagmomPredictor(str(checkpoint),str(head_checkpoint),device=device,seed_mode='raw')
            for model in [self.moment_predictor.backbone,self.moment_predictor.head]:
                for p in model.parameters():p.requires_grad_(False)

    def initial_moments(self,atoms,seeds,signs=None):
        if self.moment_predictor is None:return np.asarray(seeds,float)
        predicted=np.asarray(self.moment_predictor.predict_moments(atoms,seeds),float)
        if predicted.shape!=(len(atoms),) or not np.isfinite(predicted).all():raise ValueError('Invalid moment-head output')
        if signs is not None:
            signs=np.asarray(signs);predicted=signs*np.maximum(abs(predicted),.1)
        return predicted

    def validate(self, atoms):
        missing=set(map(int,atoms.numbers))-self.elements
        if missing: raise ValueError(f'Checkpoint does not support atomic numbers {sorted(missing)}')

    def energy(self, atoms, moments):
        self.validate(atoms)
        return self.runtime.energy(atoms, moments)

    def prepare_energy_gradient(self, atoms):
        from prophet_spin.graph import sample_from_atoms
        self.validate(atoms)
        rt, torch = self.runtime, self.torch
        batch = rt._batch([sample_from_atoms(atoms, np.zeros(len(atoms)))])
        species, edge_index, edge_attr, batch_idx, num_graphs = rt.model._common_inputs(batch)

        def energy_gradient(moments):
            with torch.enable_grad():
                leaf = torch.as_tensor(moments, device=rt.dev, dtype=batch.pos.dtype).requires_grad_(True)
                energies, _ = rt.model.model.forward_features(
                    species, batch.pos, edge_attr, edge_index, batch.cell, batch_idx, magmoms=leaf
                )
                energy = rt.model._energy_per_graph(energies, batch_idx, num_graphs).sum()
                gradient, = torch.autograd.grad(energy, leaf)
            return float(energy.detach().cpu()), gradient.detach().cpu().numpy()

        return energy_gradient

    def energy_gradient(self, atoms, moments):
        return self.prepare_energy_gradient(atoms)(moments)

    def joint_efs(self, atoms, moments):
        """Differentiate the same model energy in structure and spin coordinates."""
        from ase.stress import full_3x3_to_voigt_6_stress
        from prophet_spin.graph import sample_from_atoms

        self.validate(atoms)
        rt, torch = self.runtime, self.torch
        batch = rt._batch([sample_from_atoms(atoms, moments)])
        species, edges, shifts, batch_idx, num_graphs = rt.model._common_inputs(batch)
        with torch.enable_grad():
            pos = batch.pos.detach().requires_grad_(True)
            spins = batch.magmoms.detach().requires_grad_(True)
            strain = torch.zeros_like(batch.cell, requires_grad=True)
            symmetric = (strain + strain.transpose(-1, -2)) / 2
            strained_pos = pos + pos @ symmetric[0]
            strained_cell = batch.cell + batch.cell @ symmetric
            node_energy, _ = rt.model.model.forward_features(
                species, strained_pos, shifts, edges, strained_cell, batch_idx, magmoms=spins
            )
            energy = rt.model._energy_per_graph(node_energy, batch_idx, num_graphs).sum()
            pos_grad, strain_grad, spin_grad = torch.autograd.grad(
                energy, (pos, strain, spins), materialize_grads=True
            )
            stress = strain_grad[0] / abs(torch.linalg.det(batch.cell[0]))
        return dict(energy=float(energy.detach().cpu()),
                    forces=-pos_grad.detach().cpu().numpy(),
                    stress=full_3x3_to_voigt_6_stress(stress.detach().cpu().numpy()),
                    moment_gradient=spin_grad.detach().cpu().numpy().reshape(len(atoms)))

    def supports_exchange_head(self):
        return (self.runtime.config.get('heisenberg_mode', True)
                and self.runtime.model.model.exchange is not None)

    def efs(self,atoms,moments):
        self.validate(atoms)
        r=self.runtime.efs(atoms,np.asarray(moments))
        return dict(energy=float(r['energy']),forces=np.asarray(r['forces']),stress=np.asarray(r['stress_voigt']))

    def exchange_bonds(self,atoms,moments,bonds):
        """Read directed head terms retaining lattice offsets, then sum reverse edges.

        Return meV per unique physical bond in the normalized ±1 spin convention.
        Never use PairHamiltonian's atom-pair aggregation: it loses lattice images.
        """
        from prophet_spin.graph import sample_from_atoms
        from prophet_spin.backbone import MagmomGraft,polynomial_cutoff
        torch=self.torch;rt=self.runtime;self.validate(atoms)
        if not rt.config.get('heisenberg_mode',True) or rt.model.model.exchange is None:
            raise ValueError('Checkpoint has no supported bilinear exchange head')
        captured={}
        def hook(module,args,out):captured['args']=args
        handle=rt.model.model.exchange.register_forward_hook(hook)
        try:
            with torch.no_grad():
                b=rt._batch([sample_from_atoms(atoms,moments)]);rt.model.forward_energy(b)
                _,edges,shifts,_,_=rt.model._common_inputs(b)
                h,mm,dist,send,recv,_=captured['args'];ex=rt.model.model.exchange
                if not torch.equal(send,edges[0]) or not torch.equal(recv,edges[1]):raise ValueError('Exchange edge order changed')
                q=mm[send]**2+mm[recv]**2
                features=torch.cat([h[send]+h[recv],MagmomGraft._basis(dist,ex.r_centers,ex.r_width),MagmomGraft._basis(q,ex.q_centers,ex.q_width)],dim=-1)
                directed=.5*ex.mlp(features).squeeze(-1)*ex.branch_scales[0]*polynomial_cutoff(dist,ex.r_max)
                values=(1000*directed*abs(mm[send]*mm[recv])).cpu().numpy()
                edges=edges.cpu().numpy();shifts=np.rint(shifts.cpu().numpy()).astype(int)
        finally:handle.remove()
        def canonical(i,j,t):
            key=(int(i),int(j),*map(int,t));rev=(int(j),int(i),*map(int,-np.asarray(t)));return min(key,rev)
        aggregated={}
        # Model displacement = pos[send]-pos[recv]+shift@cell.
        # Physical bond convention = pos[j]+shift_j@cell-pos[i].
        for i,j,t,val in zip(edges[1],edges[0],shifts,values):
            k=canonical(i,j,t);aggregated[k]=aggregated.get(k,0.)+float(val)
        result=[]
        for i,j,t,_ in bonds:
            k=canonical(i,j,t)
            if k not in aggregated:
                dist=np.linalg.norm(atoms.positions[j]+np.asarray(t)@atoms.cell-atoms.positions[i])
                if dist<rt.model.graph_cutoff-1e-5:raise ValueError('Missing in-cutoff periodic bond')
            result.append(aggregated.get(k,0.))
        return np.array(result)
