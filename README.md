# MagBench

MagBench is a five-dimensional benchmark for magnetic interatomic potentials. A model is evaluated on 191 magnetic materials for the magnetic ground state, the energy above the Materials Project hull, phonon spectra, exchange parameters J, and the volume dependence of J.

This repository contains the evaluation code. The benchmark data (inputs, DFT reference targets, raw reference calculations and reference results) are hosted on Hugging Face: https://huggingface.co/datasets/kairosmaterial/Magbench.

## Repository layout

| Path | Content |
|---|---|
| `benchmark_runner/magbench/` | Runner and scorer: magnetic-state search, joint relaxation, hull, phonons, J, volume-exchange coupling and the five scores; command-line tool `magbench` |
| `benchmark_runner/vendor/` | Prophet-Spin v2 inference source used for the reference evaluation |
| `benchmark_runner/operations/` | Environment patch for the reference software stack |
| `tools/fix_magnetovolume_designs.py` | Script that produced the corrected volume-exchange designs of data version v0.2.2 |

## Data

| Component | Materials | Content |
|---|---:|---|
| Magnetic ground state and MP hull | 191 | Final structures of the original DFT relaxations (EXTXYZ), experimental and DFT moments, MP hull labels |
| Volume-exchange coupling | 133 | Volume-strain designs and reference slopes ∂J/∂ln V |
| Phonon spectra | 110 | Displaced supercells, reference sampling points, DFT frequencies and force constants |
| Magnetic exchange J | 172 | Exchange bonds, shells, energy-mapping designs and DFT J |

In the dataset, `inputs/` is used for model inference and `targets/` for scoring. The current data version is v0.2.2; the scoring protocol is v0.2.1.

```sh
huggingface-cli download kairosmaterial/Magbench --repo-type dataset --local-dir data
```

## Scoring protocol (v0.2.1)

Each of the five dimensions carries 0.20 of the total score, and models are ranked by total score in descending order. Every dimension is scored per material first and then averaged with equal weights over the fixed list of materials of that dimension. A material that fails the magnetic ground-state check scores zero in every dimension.

| Metric | Scoring rule |
|---|---|
| Magnetic ground-state search | Up to 32 collinear sign patterns are screened in the input cell, including the experimental sign pattern. Joint relaxation of at most 500 steps is carried out only if a sign pattern equivalent to the reference is among the top three. Crystal-symmetry permutations are constructed with a tolerance of 0.01 Å on the input cell, and a global flip is allowed. A passing configuration must lie within 1 meV/atom of the lowest converged candidate of the model, and the magnitude on every magnetic site must deviate from DFT by at most 25%. |
| MP hull | Uses the model configuration that passed the ground-state check. 50% for the side of the hull (>0 versus ≤0) and 50% for numerical accuracy, `2^(-absolute error / 10 meV/atom)`. |
| Phonon spectrum | Uses the selected configuration and the model moments. Atomic positions and lattice are refined to a force threshold of 0.01 eV/Å in at most 500 steps. The score is zero if the lowest frequency is below −0.1 THz; a stable spectrum scores `0.5 + 0.5 × 2^(-W₁ / 1 THz)`. |
| J | Uses the DFT reference structure and moments. 50% for the fraction of correct signs; signs are compared only for parameters with `abs(J_DFT) ≥ 0.2 meV`. 50% for the numerical accuracy of all parameters, `2^(-R)`, with the error scale `max(0.2 × abs(J_DFT), 0.2 meV)`. Both parts use the shell weights 3 : 2.5 : 2 : 1.5 : 1, and every further shell has weight 1. Parameters of the same shell share the weight of that shell equally. |
| Volume-exchange coupling | Uses the DFT reference structure and moments. 50% for the fraction of correct signs; signs are compared only for parameters whose DFT slope has an absolute value of at least 1 meV. 50% for the numerical accuracy of all slopes, `2^(-R)`, with the error scale `max(0.2 × abs(DFT slope), 1 meV)`. All slope parameters have equal weight. |

For J and the volume-exchange coupling, `R` is the normalised root-mean-square error of a material. If no parameter reaches the sign threshold, the sign part of that material is zero. J and the slopes may be obtained by energy mapping with the model or by an equivalent exchange-head readout. The exchange convention is `E = E₀ + Σ Jₖ sᵢsⱼ`, with every physical bond counted once, `sᵢ = ±1`, and positive J antiferromagnetic.

## Usage

To evaluate a model from a checkpoint, set up the environment as described in [`benchmark_runner/README.md`](benchmark_runner/README.md), then run the magnetic ground-state search with joint relaxation, the candidate check, the downstream properties and the scoring. The model weights are supplied by the evaluator.

With existing model predictions, only NumPy and SciPy are needed. Score `predictions.json` together with the phonon prediction files next to it; the field format is given in `targets/scoring.json` of the dataset.

```sh
python -m pip install ./benchmark_runner
magbench score --targets data/targets --predictions /path/to/predictions.json --output scores.json
```

## Reference result

Prophet-Spin v2, with moment-head initialisation and exchange-head readout, scores **0.43731 / 1** under protocol v0.2.1.

| Magnetic ground state | MP hull | Phonon spectrum | J | Volume-exchange coupling |
|---:|---:|---:|---:|---:|
| 0.15288 | 0.09850 | 0.05784 | 0.06150 | 0.06659 |

The complete per-material scores are in `results/prophet_spin_v2/scores.json` of the dataset.

## License

The code in this repository is released under the MIT License (see [LICENSE](LICENSE)). The benchmark data are released under CC BY 2.0 (see the dataset page).
