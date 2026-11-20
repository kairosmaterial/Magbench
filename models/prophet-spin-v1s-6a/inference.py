"""Public 6 Å checkpoint adapter for the unchanged benchmark runner."""
import argparse
from pathlib import Path
import sys
import numpy as np
from magbench.adapters import ProphetSpinV1


class Model(ProphetSpinV1):
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
                directed=.5*ex.mlp(features).squeeze(-1)*polynomial_cutoff(dist,ex.r_max)
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--public-source', type=Path, default=Path('prophet'))
    options, remaining = parser.parse_known_args()
    source = options.public_source.resolve()
    if not (source/'prophet_spin').is_dir():
        parser.error('Public source checkout must contain prophet_spin/')
    sys.path.insert(0, str(source))
    sys.argv = [sys.argv[0], *remaining]
    from magbench import adapters, cli
    adapters.ProphetSpinV1 = Model
    cli.main()
