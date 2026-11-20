#!/usr/bin/env python3
"""Score predictions: python score.py predictions.json --output scores.json"""
import argparse,json
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.stats import wasserstein_distance

def load(p):
    return json.loads(Path(p).read_text())

def vector(value,n):
    a=np.asarray(value,dtype=float)
    if a.shape!=(n,) or not np.isfinite(a).all():
        raise ValueError('Missing, nonfinite, or incorrectly sized parameter/moment array')
    return a

def continuous(error):
    return float(np.exp2(-min(float(error),1075.0)))

def ground_match(pred,target,natoms):
    if pred.get('reference_periodicity_match',True) is not True:
        return False
    m=vector(pred.get('magmoms_muB'),natoms)[target['magnetic_site_indices']]
    ref=np.array(target['reference_signs']); minimum=np.array(target['minimum_abs_moment_muB'])
    for permutation in target['symmetry_permutations']:
        p=np.asarray(permutation,dtype=int)
        if np.all(abs(m)>=minimum[p]) and (np.array_equal(np.sign(m),ref[p]) or np.array_equal(np.sign(m),-ref[p])):
            return True
    return False

MAX_RELATIVE_MOMENT_ERROR = .25


def ground_alignment(prediction, target, natoms):
    """Match signs and magnitudes under the same crystal symmetry."""
    if prediction.get('reference_periodicity_match', True) is not True:
        return None
    ids = np.asarray(target['magnetic_site_indices'], dtype=int)
    predicted = vector(prediction.get('magmoms_muB'), natoms)[ids]
    signs = np.asarray(target['reference_signs'])
    minimum = np.asarray(target['minimum_abs_moment_muB'])
    reference = target.get('reference_magmoms_muB')
    amplitude = None if reference is None else abs(vector(reference, natoms)[ids])
    if amplitude is not None and np.any(amplitude <= 0):
        raise ValueError('Magnetic reference sites must have nonzero DFT moments')
    best = None
    for permutation in target['symmetry_permutations']:
        order = np.asarray(permutation, dtype=int)
        reference_signs = signs[order]
        if not (np.array_equal(np.sign(predicted), reference_signs) or
                np.array_equal(np.sign(predicted), -reference_signs)):
            continue
        if np.any(abs(predicted) < minimum[order]):
            continue
        if amplitude is None:
            return {}
        expected = amplitude[order]
        error = float(np.max(abs(abs(predicted) - expected) / expected))
        if error <= MAX_RELATIVE_MOMENT_ERROR + 1e-12 and (best is None or error < best):
            best = error
    return None if best is None else {'max_relative_moment_error': best}


GROUND_STATE_TOLERANCE_MEV_ATOM = 1.0


def select_ground_candidate(prediction, target, natoms):
    """Select the lowest experimental match within 1 meV/atom of the model minimum."""
    candidates = prediction['converged_candidates']
    if not candidates or natoms < 1:
        raise ValueError('Missing converged magnetic candidates')
    energies = [float(candidate['energy_eV']) for candidate in candidates]
    if not np.isfinite(energies).all():
        raise ValueError('Nonfinite candidate energy')
    minimum = min(energies)
    for candidate, energy in sorted(zip(candidates, energies),
                                    key=lambda row: (row[1], row[0]['seed_index'])):
        gap = (energy - minimum) * 1000 / natoms
        if gap > GROUND_STATE_TOLERANCE_MEV_ATOM + 1e-9:
            break
        alignment = ground_alignment(candidate, target, natoms)
        if alignment is not None:
            return candidate, dict(seed_index=candidate['seed_index'], gap_meV_atom=gap,
                                   lowest_energy_eV=minimum, selected_energy_eV=energy,
                                   **alignment)
    return None, None


def parameter_error(predicted, reference, relative_scale, floor, weights=None):
    ref = np.asarray(reference,dtype=float)
    pred = vector(predicted,len(ref))
    normalized = abs(pred-ref)/np.maximum(relative_scale*abs(ref),floor)
    if weights is None:
        return float(np.linalg.norm(normalized)/np.sqrt(len(ref)))
    return float(np.linalg.norm(normalized*np.sqrt(weights/weights.sum())))


def exchange_shell_weights(parameters, shell_weights, outer_weight):
    shells = [item['shell_number'] for item in parameters]
    counts = Counter(shells)
    if any(not isinstance(shell,int) or shell < 1 for shell in shells):
        raise ValueError('Invalid exchange shell number')
    weights = [(shell_weights[shell-1] if shell <= len(shell_weights) else outer_weight) / counts[shell]
               for shell in shells]
    weights = np.asarray(weights,dtype=float)
    if not np.isfinite(weights).all() or np.any(weights <= 0) or not len(weights):
        raise ValueError('Invalid exchange shell weights')
    return weights


def phonon_error(ref_dir,pred_file,threshold):
    with np.load(ref_dir/'reference.npz',allow_pickle=False) as r,np.load(pred_file,allow_pickle=False) as p:
        ref=r['mesh_frequencies_THz'];mesh=np.asarray(p['mesh_frequencies_THz'],float);band=np.asarray(p['band_frequencies_THz'],float)
        if mesh.shape!=ref.shape or band.shape!=(len(r['band_qpoints']),ref.shape[1]):
            raise ValueError('Frequency array dimensions differ from the reference sampling')
        if not np.isfinite(mesh).all() or not np.isfinite(band).all():
            raise ValueError('Nonfinite frequencies')
        for key in ['mesh_qpoints','band_qpoints']:
            q=np.asarray(p[key],float);rq=r[key]
            if q.shape!=rq.shape or not np.isfinite(q).all() or not np.allclose(q-rq-np.rint(q-rq),0,atol=1e-8,rtol=0):
                raise ValueError('q-point sampling/order differs')
        minimum=float(min(mesh.min(),band.min()))
        if minimum<threshold:
            return dict(stable=False,minimum_frequency_THz=minimum,W1_THz=None)
        w=np.repeat(r['mesh_weights'],ref.shape[1]);w=w/w.sum()
        w1=float(wasserstein_distance(ref.ravel(),mesh.ravel(),u_weights=w,v_weights=w))
        return dict(stable=True,minimum_frequency_THz=minimum,W1_THz=w1)

def evaluate(reference,predictions,prediction_root,*,ground_only=False):
    reference=Path(reference);prediction_root=Path(prediction_root);cfg=load(reference/'scoring.json');gs=load(reference/'ground_state.json');hull=load(reference/'hull.json');materials=load(reference/'materials.json');cohorts=cfg['cohorts'];cohort_sets={k:set(v) for k,v in cohorts.items()}
    canonical={}
    for key,value in predictions.items():
        k=f'{int(key):03d}'
        if k in canonical:raise ValueError('Duplicate material IDs')
        canonical[k]=value
    rows=[]
    for material in materials:
        key=material['id'];p=canonical.get(key,{});p=p if isinstance(p,dict) else {};eligible=[k for k,s in cohort_sets.items() if key in s];scores={k:(0.0 if k in eligible else None) for k in cohorts};details={}
        try:
            if 'converged_candidates' in p:
                candidate, selection = select_ground_candidate(p,gs[key],hull[key]['natoms'])
                passed = candidate is not None
                if passed:
                    p = {**p, **candidate}
                    details['ground_state'] = selection
            else:
                passed = ground_alignment(p,gs[key],hull[key]['natoms']) is not None
        except (ValueError,TypeError,KeyError,IndexError):
            passed = False
        scores['ground_state']=float(passed)
        if not passed:
            details['gate']='ground_state_incorrect_or_missing'
        elif not ground_only:
            h=hull[key]
            try:
                energy=float(p['energy_eV'])
                if not np.isfinite(energy):raise ValueError('Nonfinite energy')
                model_hull=(energy+h['mp2020_correction_eV'])/h['natoms']-h['mp_hull_energy_per_atom_eV']
                dft_hull = h['reference_energy_above_hull_eV_atom']
                error = abs(model_hull - dft_hull)*1000
                sign_match = (model_hull > 0) == (dft_hull > 0)
                hull_cfg = cfg['hull']
                sign_score = hull_cfg.get('sign_weight',0.0)*float(sign_match)
                accuracy = hull_cfg.get('accuracy_weight',1.0)*continuous(error/hull_cfg['scale_meV_atom'])
                scores['hull'] = sign_score + accuracy
                details['hull'] = dict(predicted_eV_atom=model_hull, reference_eV_atom=dft_hull,
                                       absolute_error_meV_atom=error, sign_match=sign_match,
                                       sign_contribution=sign_score, accuracy_contribution=accuracy)
            except (ValueError,TypeError,KeyError) as e:details['hull']=dict(failed=str(e))
            for dimension,folder,pred_key,ref_key in [('J','exchange','J_meV','reference_J_meV'),('magnetovolume','magnetovolume','dJ_dlnV_meV','reference_dJ_dlnV_meV')]:
                if dimension not in eligible:continue
                try:
                    reference_data = load(reference/folder/f'{key}.json')
                    target = np.asarray(reference_data[ref_key],dtype=float)
                    prediction = vector(p.get(pred_key),len(target))
                    c = cfg[dimension]
                    weights = None
                    if dimension == 'J' and 'shell_weights' in c:
                        parameters = reference_data['parameters']
                        if [parameter['parameter_index'] for parameter in parameters] != list(range(len(target))):
                            raise ValueError('Exchange parameter indices do not match the reference J order')
                        weights = exchange_shell_weights(parameters,c['shell_weights'],c['outer_shell_weight'])
                    error = parameter_error(prediction,target,c['relative_scale'],c['absolute_floor_meV'],weights)
                    accuracy = continuous(error)
                    details[dimension] = dict(normalized_RMS=error)
                    if dimension == 'J' or 'sign_weight' in c:
                        sign_mask = np.abs(target) >= c.get('sign_floor_meV', 0.0)
                        signs_match = np.sign(prediction[sign_mask]) == np.sign(target[sign_mask])
                        sign_weights = weights[sign_mask] if weights is not None else None
                        matched = int(np.count_nonzero(signs_match))
                        sign_accuracy = float(np.average(signs_match, weights=sign_weights)) if signs_match.size else None
                        sign = c.get('sign_weight', 0.0) * (sign_accuracy if sign_accuracy is not None else 0.0)
                        accuracy *= c.get('accuracy_weight',1.0)
                        details[dimension].update(sign_matches=matched,parameters=len(target),
                                                  sign_parameters=signs_match.size,
                                                  weighted_sign_accuracy=sign_accuracy,
                                                  sign_contribution=sign,accuracy_contribution=accuracy)
                        scores[dimension] = sign + accuracy
                    else:
                        scores[dimension] = accuracy
                except (ValueError,TypeError,KeyError) as e:details[dimension]=dict(failed=str(e))
            if 'phonons' in eligible:
                try:
                    pf=(prediction_root/p.get('phonon_file',f'phonons/{key}.npz')).resolve()
                    if not pf.is_relative_to(prediction_root.resolve()):raise ValueError('Phonon file outside prediction directory')
                    phonon_cfg = cfg['phonons']
                    result = phonon_error(reference/'phonons'/key,pf,phonon_cfg['stability_threshold_THz'])
                    stability = float(result['stable'])
                    spectrum = continuous(result['W1_THz']/phonon_cfg['W1_scale_THz']) if result['stable'] else 0.0
                    result['stability_contribution'] = phonon_cfg.get('stability_weight',0.0)*stability
                    result['spectrum_contribution'] = phonon_cfg.get('spectrum_weight',1.0)*spectrum
                    scores['phonons'] = result['stability_contribution'] + result['spectrum_contribution']
                    details['phonons'] = result
                except (OSError,ValueError,TypeError,KeyError) as e:details['phonons']=dict(failed=str(e))
        contribution=sum(cfg['weights'][k]*scores[k]/len(cohorts[k]) for k in eligible)
        rows.append(dict(id=key,name=material['name'],ground_state_pass=passed,scores=scores,weighted_contribution_to_total=contribution,details=details))
    dimensions={}
    for key,ids in cohorts.items():
        mean=float(sum(r['scores'][key] for r in rows if r['id'] in cohort_sets[key])/len(ids));dimensions[key]=dict(materials=len(ids),mean_material_score=mean,weight=cfg['weights'][key],weighted_score=mean*cfg['weights'][key])
    component_names = {'hull': ('sign', 'accuracy'), 'phonons': ('stability', 'spectrum'),
                       'J': ('sign', 'accuracy')}
    if 'sign_weight' in cfg.get('magnetovolume', {}):
        component_names['magnetovolume'] = ('sign', 'accuracy')
    for key, components in component_names.items():
        if key not in dimensions:
            continue
        dimension = dimensions[key]
        factor = dimension['weight']/dimension['materials']
        for component in components:
            dimension[f'{component}_weighted_score'] = factor*sum(
                row['details'].get(key,{}).get(f'{component}_contribution',0.0) for row in rows)
    total=sum(x['weighted_score'] for x in dimensions.values());assert abs(total-sum(r['weighted_contribution_to_total'] for r in rows))<1e-10
    result = dict(total_score=total, maximum_score=1.0, dimensions=dimensions, materials=rows)
    if 'protocol_version' in cfg:
        result['protocol_version'] = cfg['protocol_version']
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('predictions',type=Path);parser.add_argument('--reference',type=Path,default=Path(__file__).resolve().parent);parser.add_argument('--output',type=Path,default=Path('scores.json'));args=parser.parse_args();result=evaluate(args.reference,load(args.predictions),args.predictions.resolve().parent);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='materials'},indent=2))
