# MagBench protocol v0.2.1

MagBench measures magnetic ground-state search, energy relative to the Materials Project hull, phonon spectra, exchange parameters J, and volume–exchange derivatives dJ/dlnV. Each dimension contributes at most 0.20 to a total of 1.00. Larger totals rank first. Within each dimension, score each material first and average over its fixed cohort, including failures as zero. The delivered scorer and reference arrays define the numerical protocol.

<!-- cohorts:start -->
| Dimension | Fixed cohort | Total weight |
|---|---:|---:|
| Ground state | 191 | 0.20 |
| MP hull with spin | 191 | 0.20 |
| Phonons with spin | 111 | 0.20 |
| Exchange J | 172 | 0.20 |
| dJ/dlnV | 133 | 0.20 |
<!-- cohorts:end -->

Exact memberships, parameter ordering, thresholds and weights are in `targets/scoring.json`; material IDs and names are in `targets/materials.json`. Sources: delivered component 01 `targets/scoring.json`, runner `physics.py`, `scoring.py`, `selection.py`, and component 06 README. The scorer and runner stay in `benchmark_runner/magbench/`; `docs/source_integrity.json` records their SHA-256 values. Inputs and targets are hosted in the separate Hugging Face dataset, not in this code repository.

## What the model receives

The merged `inputs/` contains the starting DFT cells, species, fractional coordinates, designated magnetic-site indices, fixed cohort lists, screening reference signs and their symmetry permutations, prescribed exchange geometries/sign patterns/features, periodic bond catalogs, volume strains, phonon supercell and primitive matrices, masses, displacement distances, and reference q-point sampling. The screening sign reference intentionally includes experimental sign information. Targets contain DFT moments, hull labels and corrections, J and slope reference arrays, and phonon reference frequencies; they are used for selection/scoring outside the inference phase. The post-search selection record supplies signed DFT moments for J and volume coupling. Thus the delivered procedure is not blind to all reference information.

Ground-state search keeps the supplied composition, cell periodicity and atom order; structural relaxation is allowed but supercell expansion for search is not. Map final moments to the original atomic order. Phonon displacements and energy-mapping geometries use the supplied supercells for their respective property calculations.

## Candidate enumeration and screening

Fix the first magnetic sign to +1 to remove global-reversal duplicates. For up to six magnetic sites, enumerate tails in the order of `itertools.product((1,-1), repeat=n-1)`, capped at 32 states. For more than six sites, start with all +1 and draw unique tails using NumPy `default_rng(20261118)` until 32 states exist. Normalize the supplied reference sign pattern by its first sign and replace the last seed with it if it is absent. Use at most 32 patterns in the supplied cell.

The default seed amplitude is 3 muB. Non-magnetic sites remain zero. With a moment predictor, use its amplitudes while preserving the candidate signs. Without one, optimize the moments at fixed geometry under the sign bounds using the delivered projected Adam procedure. Its defaults are 500 steps, learning rate 0.04, projected-gradient tolerance 0.001 eV/muB, beta1=0.9, beta2=0.999, epsilon=1e-8, and moment bound ±8 muB. Positive/negative seed signs constrain moments to [0,8]/[-8,0]; zero signs fix them to zero. Return the lowest-energy visited moments if the step cap is reached. Evaluate screening energies at the resulting moments.

Sort by energy, breaking ties by seed index, and take the first three states. If none has reference-equivalent signs under a recorded crystal symmetry permutation or global reversal, fail the material before joint relaxation. This precheck tests signs only. The permutations are precomputed with spglib at 0.01 angstrom symmetry tolerance.

## Joint relaxation and matching

For each shortlisted state, jointly relax positions, cell and designated magnetic-site moments with ASE FIRE and `SpinCellFilter`, capped at 500 steps per candidate. The moment coordinate scale is 0.5 angstrom/muB and moments are clipped to ±8 muB. Non-magnetic moments stay zero. The energy, forces, cell stress and moment gradient come from the same model energy.

A candidate converges only when all limits hold at one step: maximum atomic force <0.05 eV/angstrom, maximum generalized cell force <0.05 eV/angstrom, absolute change of total cell energy <0.001 eV, and maximum site moment change <0.05 muB. Energy and moment changes require a previous step. A candidate reaching the cap without convergence fails. Save all converged candidates and failed-candidate diagnostics.

Find the minimum energy over converged candidates. In increasing energy and seed-index order, accept the first candidate whose energy gap is ≤1 meV/atom, whose magnetic-site signs match a reference permutation up to a single global flip, and whose moments meet both the collapse and amplitude criteria. The collapse threshold per site is `max(0.001 muB, 0.1*abs(m_DFT))`. Every magnetic-site relative amplitude error `abs(abs(m_model)-abs(m_DFT))/abs(m_DFT)` must be ≤0.25. The same symmetry permutation applies to signs, collapse thresholds and magnitudes. A false `reference_periodicity_match` rejects the state. The scorer allows numerical boundary slack of 1e-9 meV/atom and 1e-12 in the amplitude test. Nonfinite or incorrectly sized arrays fail.

Ground-state score is 1 for a passing candidate and 0 otherwise. The ground-state gate sets all dimensions for that material to zero if it fails. Fixed cohort denominators never shrink to the successful subset. The selected candidate is the lowest-energy experimental match within the window, which can differ from the absolute model minimum.

The `select` command requires all ground-state cohort records to be terminal (converged or recorded failure) before any property phase. Its record records selected seed indices and signed DFT moments. Materials without a selected candidate skip all properties. Hull uses the selected candidate's final model energy; it requires no extra model evaluation.

## MP hull with spin score

Let N be the supplied atom count, E the selected raw model total energy in eV, C the stored MP2020 correction in eV, and H the stored MP hull energy per atom. Compute `h_model = (E+C)/N-H`; keep negative values. Use the fixed public MP 2023-02-07 GGA/GGA+U MP2020 snapshot. Raw model energies must share the reference VASP energy zero.

With `D = 1000*abs(h_model-h_DFT)` in meV/atom:

```
S_hull = 0.5 * I[(h_model > 0) == (h_DFT > 0)] + 0.5 * 2^(-D/10).
```

Zero belongs to the on-or-below-hull class. Missing or nonfinite energy gives zero.

## Phonons with spin score

Start with the selected relaxed candidate and its model moments. Hold these moments fixed and refine positions and cell with FIRE to maximum atomic and generalized cell force <0.01 eV/angstrom, capped at 500 steps. Use the last frame at the cap, recording residuals and convergence. Use the supplied supercell, primitive matrix, masses, displacement distance, frequency conversion factor and symmetry tolerance per material. If spglib reports `spacegroup search failed`, keep the actual geometry and use displacements without point-group reduction.

Subtract the undisplaced supercell residual forces, then remove the mean force of each displaced supercell. Produce and symmetrize force constants using Phonopy, including its translational acoustic sum rule. No non-analytical correction is applied. Use the supplied mesh and band q points in their exact order; q points can differ from reference by reciprocal lattice integers within 1e-8. Frequency-array shapes must match and all values must be finite.

Take the minimum frequency across mesh and band samples. If it is below −0.1 THz, `S_phonons=0`. Otherwise:

```
S_phonons = 0.5 + 0.5 * 2^(-W1 / 1 THz).
```

W1 is the Wasserstein-1 distance between signed model and DFT mesh-frequency distributions. Repeat each reference mesh weight across all branches and normalize to sum one. The band samples enter stability but not W1. Missing files, invalid sampling or nonfinite frequencies give zero.

## Exchange convention and admissible routes

J and dJ/dlnV use the supplied original DFT reference geometry and signed DFT moments, not the model-selected geometry or amplitudes. All parameters use:

```
E = E0 + sum_unique_physical_bonds J_k * s_i * s_j,   s_i = ±1.
```

Each periodic physical bond is counted once; positive J favors antiferromagnetism. Bond entries are `[atom_i,atom_j,integer_shift_of_j,parameter_index]` with zero-based indices. Parameter arrays follow the supplied `parameter_index` order. Magnitude products are absorbed into J, not multiplied a second time in this convention.

Two routes are supported by the delivered runner: energy mapping and an equivalent exchange readout. The default requests `exchange-head`; unsupported readout falls back to energy mapping. Each prediction records the route actually used.

For energy mapping, map fixed DFT moment magnitudes from the starting cell to each unchanged design geometry, then multiply by each prescribed state sign. The lattice transform must be integer within 0.003 and the same-species sites must match within 0.25 angstrom after periodic wrapping. A signed design site with magnitude below 0.001 muB fails. Evaluate every prescribed state at fixed moments. Build the matrix from one offset column per `offset_cells` entry and the supplied state features, dividing features and total energy by that state's atom count. Scale columns by their norm with a floor of 1e-12. Require full matrix rank at tolerance 1e-9; solve least squares with `rcond=1e-10`, undo the column scaling, discard offset coefficients, and multiply energy coefficients by 1000 for meV.

For readout, retain periodic lattice shifts, combine reverse directed half-bond contributions, convert eV coefficients and fixed DFT magnitude products into meV in the normalized-sign convention, and average equivalent physical bonds for each prescribed parameter. Finite-range unsupported bonds may have J=0. Missing in-range terms must not be silently dropped.

An effective pair coupling derived analytically from the model energy is an accepted exchange-readout route.

For volume coupling, use the supplied isotropic volume deltas (−0.01, −0.005, +0.005, +0.01), scale cell lengths by `(1+delta)^(1/3)` at fixed fractional coordinates and fixed signed DFT moments, and evaluate the same exchange route at each volume and at zero. With `x=ln(1+delta)`, solve `J(delta)-J(0) = a*x + b*x²` by least squares with `rcond=None`; the slope a is dJ/dlnV in meV. Do not substitute a different zero-strain fit.

## J score

For each parameter k, set `u_k=abs(J_model,k-J_DFT,k)/max(0.2*abs(J_DFT,k),0.2 meV)`. Shells 1–5 have weights 3, 2.5, 2, 1.5, 1; every outer shell has weight 1. Divide a shell's weight equally among its parameters to obtain w_k. The accuracy error is `R=sqrt(sum(w_k*u_k²)/sum(w_k))` over all parameters.

For signs, retain parameters with `abs(J_DFT,k) >= 0.2 meV`, normalize their weights over that subset, and take the weighted fraction A of exactly matching signs. A=0 when no parameter qualifies.

```
S_J = 0.5*A + 0.5*2^(-R).
```

A missing, nonfinite or wrong-length parameter array gives the entire material J dimension zero. Parameter-index and shell metadata must be valid.

## dJ/dlnV score

For slope t_k, set `u_k=abs(t_model,k-t_DFT,k)/max(0.2*abs(t_DFT,k),1 meV)` and `R=sqrt(mean(u_k²))` over all parameters with equal weight. A is the equal-weight fraction of matching signs among slopes with `abs(t_DFT,k) >= 1 meV`, or zero if none qualifies.

```
S_dJ/dlnV = 0.5*A + 0.5*2^(-R).
```

A missing, nonfinite or wrong-length slope array gives the entire material slope dimension zero. The implementation caps the exponent error at 1075 before `exp2` in all continuous accuracy terms.

## Total and ranking

For dimension d with fixed cohort C_d, let `M_d = sum(S_i,d for i in C_d)/len(C_d)`. Report the dimension contribution `0.20*M_d`; total is the sum of the five contributions. The ground-state gate is applied before each property score. Scores are not bond-pooled. Materials outside a property cohort have no score for that property.

Identical totals are ordered by model key.

## Reproducibility and versioning

The delivered runner fingerprints checkpoint bytes, moment-head bytes, all inference inputs, settings and exchange route; it refuses mixed resume states. Successful stages resume only under matching stage records. Save converged candidates, errors, selection record, model/reference versions, raw prediction JSON and adjacent phonon NPZ files. Full ground-state completion precedes properties. Diagnostic configuration overrides are not comparable leaderboard submissions.

The reference inference environment was Python 3.11.15, PyTorch 2.5.1+cu121, e3nn 0.5.8, torch-scatter 2.1.2+pt25cu121, OpenEquivariance 0.5.4, ASE 3.28.0 and Phonopy 4.1.0, with Ninja and a CUDA development toolkit for its kernels. These are reference model dependencies, not requirements for offline scoring. The reference kernel patch is in `benchmark_runner/operations/`.

Protocol releases must identify changes in rules, reference arrays and cohorts and retain old score records; do not silently reinterpret scores across versions. The delivered input manifest retains its historical internal version 0.1.0 and runner resume stage records retain runner_version 0.6.0; the scoring protocol is 0.2.1.

## Benchmark-informed model disclosure

Every submission declares `test_set_informed`. Any use of the benchmark materials or of benchmark scores in training, validation, model or checkpoint selection requires `true` and a one-sentence `notes.disclosure`. Seed-table selection informed by benchmark materials must also be disclosed. Such entries remain listed. Declarations are retained in model cards without table markers.

## Data releases

Data version v0.2.2 corrects signs on non-magnetic species in the magnetovolume energy-mapping designs. It does not change the v0.2.1 scoring rules, cohorts, targets or exchange-readout reference scores. Energy-mapping runs must use the corrected designs. Data version v0.2.3 adds material 221 (bcc Fe) to the phonon cohort. Cohort sizes above are read from the current score records; all other reference arrays, rules and defaults are unchanged. Dataset repository, immutable revision and target hashes must be pinned in `benchmark.json`.

The repository code licence is MIT; the dataset licence is CC BY 2.0.

## Architecture metadata

Model cards declare `hyperparams.architecture.cutoff_A`, `exchange_range_A`, `n_layers` and `model_params`. Cutoffs are recorded in angstroms and retain all configured graph scales. An exchange term may require a larger neighbour list than these backbone scales. The exchange-range field describes the explicit exchange envelope or the longest representable spin-spin pair coupling; it is null only when no such coupling exists. An unset separate exchange-range option can inherit the largest graph cutoff and therefore does not imply a missing exchange term. Density-mediated pair couplings can reach twice the density radius, which must be explained in the card note. Parameter counts identify their convention and the inclusion or exclusion of a separate moment head. These descriptive fields do not change any benchmark input, reference, runner setting or score formula.

Training datasets are recorded separately in `datasets/<dataset_key>.yml` and referenced by model cards through `training_sets` (`dataset_key`, `usage`, optional `subset`). Frame counts for an unknown subset are not replaced by the full dataset count. Architecture cards retain exact parameter counts; the site displays millions to one decimal. These are reporting requirements and do not alter the benchmark scores.
