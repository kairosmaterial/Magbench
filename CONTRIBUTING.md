# Submit a model

A submission is one pull request that adds the folder `models/<model_key>/`. The key is lowercase with hyphens.

## Requirements

- The inference code is open source in a public repository.
- The evaluated weights can be downloaded from a public URL.
- Licences are stated for the code and for the weights.
- The predictions were produced with the shared runner and its default settings, on the current protocol and data version.

Weights and prediction files are hosted by the submitter at stable HTTPS addresses, for example Hugging Face, Zenodo or figshare. They are not committed to this repository.

## Files in the pull request

```text
models/<model_key>/
  <model_key>.yml    model card
  inference.py       adapter and the command that reproduces the predictions
  scores.json        output of `magbench score`
```

Nothing outside this folder is changed.

`inference.py` defines the adapter that connects the model to the runner. The interface is `initial_moments`, `energy`, `energy_gradient`, `joint_efs`, `efs` and, optionally, `exchange_bonds`; see `benchmark_runner/magbench/adapters.py` and [`benchmark_runner/README.md`](benchmark_runner/README.md).

## Model card

The card follows `tests/model-schema.yml`; unknown keys are rejected.

| Field | Content |
|---|---|
| `model_name`, `model_key`, `model_version` | Identity |
| `lifecycle` | `pending` |
| `dates.benchmark_added` | Date, `YYYY-MM-DD` |
| `authors` | Name and affiliation of each author; one with `corresponding: true` |
| `repo` | Public repository with the inference code |
| `checkpoint` | `url` and `sha256` of the evaluated weights |
| `license` | `code` and `checkpoint` |
| `architecture`, `targets` | Short architecture description; predicted quantities |
| `hyperparams.architecture` | `cutoff_A`, `exchange_range_A`, `n_layers`, `model_params` |
| `training_sets` | Data used for training and pretraining |
| `test_set_informed` | `true` if benchmark materials or benchmark scores were used in training, validation or model selection; then add one sentence in `notes.disclosure` |
| `evaluation` | `moment_initialisation` (`moment_head` or `energy_gradient`), `seed_amplitudes` (`uniform_3muB` or `model`), `exchange_route` (`energy_mapping` or `exchange_readout`), `protocol_version`, `data_version`, `runner_version` |
| `inference` | `script`, `adapter`, the exact `command`, `python_version`, pinned `dependencies` |
| `predictions` | `url`, `sha256` and `size` of `predictions.json`, and the same for the phonon prediction files |
| `metrics` | `total`, `ground_state`, `hull`, `phonons`, `J`, `magnetovolume`, `ground_state_passes` |

Optional: `paper`, `doi`, `docs`, `training_cost`, `notes`. The current versions are listed in `benchmark.json`.

## Produce predictions and scores

```sh
python -m pip install ./benchmark_runner
python models/<model_key>/inference.py <arguments recorded in the card>
magbench score --targets data/targets --predictions run/predictions.json --output models/<model_key>/scores.json
```

The reference data are downloaded as described in the [README](https://github.com/kairosmaterial/Magbench#readme). Upload `predictions.json` and the files of `run/phonons/` (as one archive, or as a directory listed in the card), and record their addresses, SHA-256 values and sizes in the card.

## Check before opening the pull request

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_submission.py <model_key> --offline --data data --predictions run/predictions.json
```

The same checks run on the pull request. There the prediction files are downloaded from the addresses in the card and the scores are recomputed with the packaged scorer; the declared metrics must equal the recomputed ones.

<!-- site:submission:end -->

## Validation and maintainer reference

A submission is one pull request that adds the folder `models/<model_key>/`. The key is lowercase with hyphens.

## Requirements

- The inference code is open source in a public repository.
- The evaluated weights can be downloaded from a public URL.
- Licences are stated for the code and for the weights.
- The predictions were produced with the shared runner and its default settings, on the current protocol and data version.

Weights and prediction files are hosted by the submitter at stable HTTPS addresses, for example Hugging Face, Zenodo or figshare. They are not committed to this repository.

## Files in the pull request

```text
models/<model_key>/
  <model_key>.yml    model card
  inference.py       adapter and the command that reproduces the predictions
  scores.json        output of `magbench score`
```

Nothing outside this folder is changed.

`inference.py` defines the adapter that connects the model to the runner. The interface is `initial_moments`, `energy`, `energy_gradient`, `joint_efs`, `efs` and, optionally, `exchange_bonds`; see `benchmark_runner/magbench/adapters.py` and [`benchmark_runner/README.md`](benchmark_runner/README.md).

## Model card

The card follows `tests/model-schema.yml`; unknown keys are rejected.

| Field | Content |
|---|---|
| `model_name`, `model_key`, `model_version` | Identity |
| `lifecycle` | `pending` |
| `dates.benchmark_added` | Date, `YYYY-MM-DD` |
| `authors` | Name and affiliation of each author; one with `corresponding: true` |
| `repo` | Public repository with the inference code |
| `checkpoint` | `url` and `sha256` of the evaluated weights |
| `license` | `code` and `checkpoint` |
| `architecture`, `targets` | Short architecture description; predicted quantities |
| `hyperparams.architecture` | `cutoff_A`, `exchange_range_A`, `n_layers`, `model_params` |
| `training_sets` | Data used for training and pretraining |
| `test_set_informed` | `true` if benchmark materials or benchmark scores were used in training, validation or model selection; then add one sentence in `notes.disclosure` |
| `evaluation` | `moment_initialisation` (`moment_head` or `energy_gradient`), `seed_amplitudes` (`uniform_3muB` or `model`), `exchange_route` (`energy_mapping` or `exchange_readout`), `protocol_version`, `data_version`, `runner_version` |
| `inference` | `script`, `adapter`, the exact `command`, `python_version`, pinned `dependencies` |
| `predictions` | `url`, `sha256` and `size` of `predictions.json`, and the same for the phonon prediction files |
| `metrics` | `total`, `ground_state`, `hull`, `phonons`, `J`, `magnetovolume`, `ground_state_passes` |

Optional: `paper`, `doi`, `docs`, `training_cost`, `notes`. The current versions are listed in `benchmark.json`.

## Produce predictions and scores

```sh
python -m pip install ./benchmark_runner
python models/<model_key>/inference.py <arguments recorded in the card>
magbench score --targets data/targets --predictions run/predictions.json --output models/<model_key>/scores.json
```

The reference data are downloaded as described in the [README](README.md). Upload `predictions.json` and the files of `run/phonons/` (as one archive, or as a directory listed in the card), and record their addresses, SHA-256 values and sizes in the card.

## Check before opening the pull request

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_submission.py <model_key> --offline --data data --predictions run/predictions.json
```

The same checks run on the pull request. There the prediction files are downloaded from the addresses in the card and the scores are recomputed with the packaged scorer; the declared metrics must equal the recomputed ones.
