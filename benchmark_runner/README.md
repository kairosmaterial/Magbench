# MagBench model evaluation

Five material-level scores, each weighted 0.2: magnetic ground state (191), MP hull (191), phonons (110), exchange J (172), and volume–exchange coupling (133). Wrong or missing ground-state order zeros all scores for that material. Fixed cohort denominators include failed predictions. Phonon minimum frequency below −0.1 THz gives zero phonon score.

## Run a model

Download the benchmark data as described in the repository README and place `inputs/` and `targets/` next to `benchmark_runner/`. Run the following commands from that directory. The `benchmark_runner/vendor/` directory contains the exact Prophet-Spin v1 runtime source used for the reference evaluation.

Install the runner in a Linux CUDA environment. The reference run used Python 3.11.15, PyTorch 2.5.1+cu121, e3nn 0.5.8, torch-scatter 2.1.2+pt25cu121, OpenEquivariance 0.5.4, ASE 3.28.0, and Phonopy 4.1.0. The runtime also needs Ninja and a CUDA development toolchain for first-use kernel compilation. Set `CUDA_HOME` to the toolkit location. For the reference PyTorch 2.5 and OpenEquivariance 0.5.4 combination, run `python benchmark_runner/operations/patch_oeq_fp32_portable.py` once in the dedicated evaluation environment.

```bash
python -m pip install ./benchmark_runner
export PYTHONPATH="$PWD/benchmark_runner/vendor${PYTHONPATH:+:$PYTHONPATH}"
checkpoint=/path/to/checkpoint.pt
moment_head=/path/to/moment-head.pt

magbench run --inputs inputs --checkpoint "$checkpoint" --moment-head "$moment_head" \
  --output run --stages ground_state
magbench select --inputs inputs --targets targets --run run --output run/selection.json
magbench run --inputs inputs --checkpoint "$checkpoint" --moment-head "$moment_head" \
  --output run --stages J magnetovolume phonons --ground-state-barrier run/selection.json
magbench score --targets targets --predictions run/predictions.json --output run/scores.json
```

Supply the checkpoint and the compatible moment-head checkpoint separately. The head initializes the moments before energy-gradient refinement. For a model without a moment head, use `--no-moment-head` in place of `--moment-head "$moment_head"` in both inference commands.

J and the volume derivative use the bilinear exchange readout by default. The readout uses the signed DFT moments and the DFT reference structure. Models without a compatible exchange readout use energy mapping. To request energy mapping explicitly, pass `--exchange-method energy-mapping`. Each material records the method used.

The head adapter retains periodic lattice shifts, adds the two directed half-bond contributions, multiplies the model's moment-product coefficient by the prescribed DFT moment magnitudes, converts eV to meV, and averages equivalent bonds within each prescribed exchange parameter. Both methods use `E = E0 + sum_unique_bonds J*s_i*s_j`, with normalized `s=±1` and positive J favoring AFM. Bonds beyond the model's finite interaction cutoff have J=0.

Ground-state inference screens at most 32 sign patterns in the supplied cell, enumerating the smaller sign spaces up to global reversal. The screening pool includes the reference sign pattern up to global reversal. The moment head supplies amplitudes when available. The material fails before relaxation if none of the three lowest screening energies is associated with a symmetry-equivalent reference sign pattern. This precheck uses signs only. Screening and final matching use the same symmetry permutations precomputed on each input DFT cell with spglib at 0.01 Å. If it passes, the three lowest screening energies go to joint FIRE relaxation of all positions, the cell and the designated magnetic-site moments, with up to 500 steps per candidate. All other sites keep zero moments during screening and relaxation. A candidate must meet all three limits at the same step: maximum force below 0.05 eV/Å, change in total cell energy below 1 meV and maximum site moment change below 0.05 μB. The cell force is checked using the same force threshold. Save every converged candidate and identify the lowest model energy. A candidate counts as an experimental ground-state match if its magnetic order matches, its final energy is at most 1 meV/atom above that minimum, and no magnetic reference site deviates from the corresponding DFT magnitude by more than 25%. The same lattice symmetry permutation applies to order and magnitudes. Use the lowest-energy candidate meeting all three conditions. The hull uses the selected candidate’s energy directly.

The `magbench select` command records completion of the entire ground-state cohort before properties start. A material without a passing candidate skips every property. Hull uses the selected candidate’s final model energy. Phonons first refine positions and cell with the selected model moments held fixed. Refinement targets a maximum atomic force and cell generalized force below 0.01 eV/Å, with a 500-step cap. Use the last frame at the cap and record the residual forces and convergence status. Phonons use that refined geometry, the same frozen model moments, the prescribed supercell and reference q points. J readout and volume–exchange coupling use the DFT reference geometry and hold the signed DFT moments fixed in the original atom order. Energy mapping is available for models without a compatible readout and evaluates the prescribed DFT design geometries and sign patterns at fixed DFT magnitudes. Volume coupling uses isotropic strains about the DFT reference volume and a fit versus ln(V/V0).

Use `--materials 007 221` for a ground-state diagnostic or a JSON `--config` to run diagnostics. The canonical defaults are in `magbench/physics.py`. Diagnostic overrides are not comparable leaderboard submissions. `run.json` fingerprints checkpoint, inputs, settings and method; successful stages resume only when these match. Inference failures remain explicit in `errors.json` and score zero.

## Scoring

- Ground state: symmetry-equivalent signs/global reversal, with a collapse threshold of max(0.001 μB, 10% of the reference site magnitude).
- Hull: award 0.5 if model and DFT are both above the hull or both on or below it. Add `0.5 * 2**(-|error|/10)` with error in meV/atom. Uses the fixed public MP 2023-02-07 GGA/GGA+U MP2020 hull and stored compatibility correction. Raw model total energies must share the reference energy zero.
- Phonons: stable if minimum over supplied mesh and band q-points is ≥−0.1 THz; stable materials score `0.5 + 0.5 * 2**(-W1/1.0)`, W1 in THz, from the weighted signed frequency distribution. Materials below the stability threshold score zero.
- J combines two equally weighted scores. For signs, average sign matches over parameters with `abs(J_DFT) >= 0.2 meV`, normalizing the weights over those parameters. If none qualify, the sign contribution is zero. For numerical accuracy, use `2**(-RMS(abs(error)/max(0.2*abs(reference),0.2 meV)))` with a weighted RMS over all parameters. Shells 1 through 5 have weights 3, 2.5, 2, 1.5 and 1. Each later shell has weight 1. Split each shell weight equally across its parameters.
- Volume coupling combines two equally weighted scores. For signs, take the fraction of matching signs among slopes with `abs(DFT dJ/dlnV) >= 1 meV`. If none qualify, the sign contribution is zero. For numerical accuracy, use `2**(-RMS(abs(error)/max(0.2*abs(reference),1 meV)))` with an equally weighted RMS over all slopes.

A missing required parameter makes that material's entire corresponding dimension zero. Scores are averaged per material, not across all bonds pooled together. Different fixed cohorts mean a material's total contribution depends on its dimension memberships.

## Hosted evaluation

`../platform` contains the authenticated Sites frontend, D1 queue and R2 multipart checkpoint storage. The GPU supervisor is `python -m magbench.worker --config worker.json`; service credentials are passed only through `MAGBENCH_EVALUATOR_TOKEN` and `MAGBENCH_SITE_ACCESS_TOKEN` environment variables. They must never enter the inference container.

The worker requires a tested Docker image with the runner and trusted adapter installed. It runs uploaded checkpoints as a non-root user with no network, read-only root filesystem, dropped capabilities, bounded CPU/RAM and a private temporary directory. Mount `inputs` only; keep `targets` outside inference. Uploads are not executed by the web server. Only the trusted evaluator can finalize scores.

```json
{"site":"http://127.0.0.1:8793","inputs":"/path/inputs","targets":"/path/targets","workdir":"/path/jobs","image":"magbench-prophet:v0.2.1","gpu":0,"memory":"48g","cpus":8,"timeout_hours":168}
```

## Development tests

Run these from the full development checkout.

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

The release validation additionally checks all 172 energy-mapping designs against the delivered J labels, all fixed cohort counts, ground-state gating, exact-score self predictions, phonon stability and q-point mismatches. Do not use self predictions as model results.
