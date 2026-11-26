# MagBench

MagBench is a five-dimensional benchmark for magnetic interatomic potentials. A model is evaluated on 191 magnetic materials for the magnetic ground state, MP hull with spin, Phonons with spin, exchange parameters J, and the volume dependence of J.

This repository contains the evaluation code. The benchmark data (inputs, DFT reference targets, raw reference calculations and reference results) are hosted on Hugging Face: https://huggingface.co/datasets/kairosmaterial/Magbench.

## Repository layout

| Path | Content |
|---|---|
| `benchmark_runner/magbench/` | Runner and scorer: magnetic-state search, joint relaxation, hull, phonons, J, volume-exchange coupling and the five scores; command-line tool `magbench` |
| `benchmark_runner/vendor/` | Reference-model inference source used for the reference evaluation |
| `benchmark_runner/operations/` | Environment patch for the reference software stack |
| `tools/fix_magnetovolume_designs.py` | Script that produced the corrected volume-exchange designs of data version v0.2.2 |

## Data

| Component | Materials | Content |
|---|---:|---|
| Magnetic ground state and MP hull with spin | 191 | Final structures of the original DFT relaxations (EXTXYZ), experimental and DFT moments, MP hull labels |
| Volume-exchange coupling | 133 | Volume-strain designs and reference slopes ∂J/∂ln V |
| Phonons with spin | 111 | Displaced supercells, reference sampling points, DFT frequencies and force constants |
| Magnetic exchange J | 172 | Exchange bonds, shells, energy-mapping designs and DFT J |

In the dataset, `inputs/` is used for model inference and `targets/` for scoring. The current data version is v0.2.3; the scoring protocol is v0.2.1.

```sh
huggingface-cli download kairosmaterial/Magbench --repo-type dataset --local-dir data
```

## Scoring protocol (v0.2.1)

Each of the five dimensions carries 0.20 of the total score, and models are ranked by total score in descending order. Every dimension is scored per material first and then averaged with equal weights over the fixed list of materials of that dimension. A material that fails the magnetic ground-state check scores zero in every dimension.

| Metric | Scoring rule |
|---|---|
| Magnetic ground-state search | Up to 32 collinear sign patterns are screened in the input cell, including the experimental sign pattern. Joint relaxation of at most 500 steps is carried out only if a sign pattern equivalent to the reference is among the top three. Crystal-symmetry permutations are constructed with a tolerance of 0.01 Å on the input cell, and a global flip is allowed. A passing configuration must lie within 1 meV/atom of the lowest converged candidate of the model, and the magnitude on every magnetic site must deviate from DFT by at most 25%. |
| MP hull with spin | Uses the model configuration that passed the ground-state check. 50% for the side of the hull (>0 versus ≤0) and 50% for numerical accuracy, `2^(-absolute error / 10 meV/atom)`. |
| Phonons with spin | Uses the selected configuration and the model moments. Atomic positions and lattice are refined to a force threshold of 0.01 eV/Å in at most 500 steps. The score is zero if the lowest frequency is below −0.1 THz; a stable spectrum scores `0.5 + 0.5 × 2^(-W₁ / 1 THz)`. |
| J | Uses the DFT reference structure and moments. 50% for the fraction of correct signs; signs are compared only for parameters with `abs(J_DFT) ≥ 0.2 meV`. 50% for the numerical accuracy of all parameters, `2^(-R)`, with the error scale `max(0.2 × abs(J_DFT), 0.2 meV)`. Both parts use the shell weights 3 : 2.5 : 2 : 1.5 : 1, and every further shell has weight 1. Parameters of the same shell share the weight of that shell equally. |
| Volume-exchange coupling | Uses the DFT reference structure and moments. 50% for the fraction of correct signs; signs are compared only for parameters whose DFT slope has an absolute value of at least 1 meV. 50% for the numerical accuracy of all slopes, `2^(-R)`, with the error scale `max(0.2 × abs(DFT slope), 1 meV)`. All slope parameters have equal weight. |

For J and the volume-exchange coupling, `R` is the normalised root-mean-square error of a material. If no parameter reaches the sign threshold, the sign part of that material is zero. J and the slopes may be obtained by energy mapping with the model or by an equivalent exchange-head readout. The exchange convention is `E = E₀ + Σ Jₖ sᵢsⱼ`, with every physical bond counted once, `sᵢ = ±1`, and positive J antiferromagnetic.

## Usage

To evaluate a model from a checkpoint, set up the environment as described in [`benchmark_runner/README.md`](benchmark_runner/README.md), then run the restricted sign-pattern screening and joint relaxation, the candidate check, the downstream properties and the scoring. The model weights are supplied by the evaluator.

With existing model predictions, only NumPy and SciPy are needed. Score `predictions.json` together with the phonon prediction files next to it; the field format is given in `targets/scoring.json` of the dataset.

```sh
python -m pip install ./benchmark_runner
magbench score --targets data/targets --predictions /path/to/predictions.json --output scores.json
```

## Reference result

Prophet-Spin v1s, with moment-head initialisation and exchange-head readout, scores **0.437756477 / 1** under protocol v0.2.1 and data v0.2.3.

| Experimental-order stability | MP hull with spin | Phonons with spin | Exchange J | dJ/dlnV |
|---:|---:|---:|---:|---:|
| 0.152879581 | 0.098499952 | 0.058284135 | 0.061501873 | 0.066590936 |

The complete per-material scores are in `results/prophet_spin_v1s/scores.json` of the dataset.

## License

The code in this repository is released under the MIT License (see [LICENSE](LICENSE)). The benchmark data are released under CC BY 2.0 (see the dataset page).

## Leaderboard

Site address: [kairosmaterial.github.io/Magbench/](https://kairosmaterial.github.io/Magbench/).

The static site compares owner-approved result records using data v0.2.3. Listed records have prediction artefacts for scorer replay; public weights and some inference code await release.

<!-- leaderboard:start -->
| Model | Total | Ground-state passes | Availability |
|---|---:|---:|---|
| [Prophet-Spin v2L](models/prophet-spin-v2l/prophet-spin-v2l.yml) | 0.605398474 | 159/191 | Awaiting public release |
| [Prophet-Spin v1L](models/prophet-spin-v1l/prophet-spin-v1l.yml) | 0.546779806 | 155/191 | Awaiting public release |
| [Prophet-Spin v1s](models/prophet-spin-v1s/prophet-spin-v1s.yml) | 0.437756477 | 146/191 | Awaiting public release |
| [Prophet-Spin v1s (6 Å)](models/prophet-spin-v1s-6a/prophet-spin-v1s-6a.yml) | 0.342340461 | 116/191 | Complete |
<!-- leaderboard:end -->

Build and preview locally:

```sh
python -m pip install -r requirements-dev.txt
python scripts/build_site.py
cd site/dist
python -m http.server
```

See [the complete protocol](PROTOCOL.md) and [protocol questions](docs/known_issues.md). No data, weights or raw predictions are stored in this code repository.

## Submitting a model

Add a model card, an inference adapter and scorer-written `scores.json` in `models/<model_key>/`. Public inference code and evaluated weights, licences, externally hosted prediction artefacts and reproducible score replay are required for new submissions.

```sh
python scripts/check_cards.py
python scripts/validate_submission.py <model_key> --cache <large-storage-cache>
python -m pytest -q
```

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for the strict schema, disclosure rule, local replay, CI checks and review steps. Protocol, data revision and target hashes are pinned in `benchmark.json`; the initial target upload is still in progress.

Training datasets have YAML records in [`datasets/`](datasets/). Model cards reference these records; dataset submission is described in [Submitting a dataset](CONTRIBUTING.md#submitting-a-dataset).

## References and acknowledgements

Experimental magnetic structures and their original papers are credited on the
site's References page, built from `docs/material_references.json`, a snapshot
of the per-material `reference.json` files in data v0.2.3. The snapshot preserves
selected MAGNDATA identifiers and DOIs; additional phase references are labelled
as such. Refresh it from the extracted dataset with
`python scripts/export_references.py --data data` before rebuilding the site. The Materials Project supplies the historical MP2020 hull reference.

For experimental exchange constants, see M. Alaei, Z. Mosleh, N. Rezaei and
A. R. Oganov, *Experimental Exchange Interaction Dataset for Magnetic Materials:
Spin Waves to MC Simulations*, Scientific Data **12**, 1832 (2025),
[doi:10.1038/s41597-025-06099-x](https://doi.org/10.1038/s41597-025-06099-x).
This compilation credits experimental exchange measurements; MagBench scores
DFT energy-mapping references.
