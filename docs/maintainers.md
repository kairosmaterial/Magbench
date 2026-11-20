# Maintainer guide


A submission is one pull request adding `models/<model_key>/`. Use a unique lowercase key with hyphens. New submissions start with `lifecycle: pending`. They must provide public open-source inference code, publicly downloadable evaluated weights, stated code and checkpoint licences, and reproducible predictions. Submitters host weights and prediction artefacts at stable HTTPS URLs, for example Hugging Face, Zenodo or figshare. Commit neither weights nor prediction artefacts to this repository.

## Required files

```text
models/<model_key>/
  <model_key>.yml
  inference.py
  scores.json
```

The inference filename may differ if the card names it. The script defines the adapter named by `inference.adapter`, supplies everything needed to connect it to the shared runner, and records the exact reproduction command. The interface is `initial_moments`, `energy`, `energy_gradient`, `joint_efs`, `efs`, and optional `exchange_bonds`; see `benchmark_runner/magbench/adapters.py` and the [runner guide](benchmark_runner/README.md). Keep all submission code inside its own model folder. Do not change other models. Changes outside that folder are flagged for maintainer review; changes to another model fail the path guard.

## Model card

`tests/model-schema.yml` rejects unknown keys, including unknown nested keys. Only `notes` allows free-form content. Required fields are:

| Field | Required content |
|---|---|
| `model_name`, `model_key`, `model_version`, `lifecycle` | Identity; lifecycle is `pending` on submission |
| `dates.benchmark_added` | ISO date, `YYYY-MM-DD` |
| `authors` | Names and affiliations, with exactly one `corresponding: true` |
| `repo` | Public HTTPS repository containing open-source inference code |
| `checkpoint` | Evaluated public weights `url`, `sha256`, optionally `size` in bytes |
| `license` | `code` and `checkpoint`, both stated |
| `architecture`, `targets` | Architecture description and predicted quantities |
| `hyperparams.architecture` | `cutoff_A` (positive number or ordered list), `exchange_range_A` (positive number or null), `n_layers` (positive integer), `model_params` (positive integer) |
| `training_sets` | Dataset references with `dataset_key`, `usage` and optional `subset` |
| `test_set_informed` | Boolean; see disclosure rule below |
| `evaluation` | `moment_initialisation`, `seed_amplitudes`, `exchange_route`, `protocol_version`, `data_version`, `runner_version`; optional hardware and wall time |
| `inference` | `script` relative to the model folder, `adapter` definition name, exact `command`, `python_version`, pinned `dependencies` using `package==version` |
| `predictions` | `url`, `sha256`, `size` of `predictions.json`; `phonons` with the same three fields for its ZIP or tar archive, or a directory `url` and a `files` manifest containing each relative `path`, `sha256` and `size` |
| `metrics` | `total`, `ground_state`, `hull`, `phonons`, `J`, `magnetovolume`, `ground_state_passes` |

Optional fields are `paper`, `doi`, `docs`, `pr_url`, `training_cost` and free-form `notes`. Metrics are the weighted dimension contributions, each out of 0.20, not the mean unweighted material scores. The total is out of 1.00.

Evaluation choices are `moment_head` or `energy_gradient`; `uniform_3muB` or `model` seed amplitudes; `energy_mapping` or `exchange_readout`. Protocol, data and runner versions must match `benchmark.json` (currently 0.2.1, 0.2.3 and 0.6.0). The installable package version, 0.1.0, is a separate identifier.

Any use of the benchmark materials or benchmark scores in training, validation, model or checkpoint selection requires `test_set_informed: true` and a one-sentence `notes.disclosure`. This includes benchmark-informed seed-table selection. The declaration remains part of the model card; entries remain listed.

Ordinary submissions cannot contain `to be provided` in required metadata. The existing owner-approved listed records have bounded metadata exceptions pinned in trusted policy while weights or inference code await public release. These exceptions cannot be claimed by other submissions. The listed records have delivered predictions and must replay; there is no replay exemption. Prophet-Spin v1 was trained on a subset of the v5 dataset.

## Run and score

Install the shared runner and validation tools in an environment appropriate to the model:

```sh
python -m pip install ./benchmark_runner
python -m pip install -r requirements-dev.txt
python models/<model_key>/inference.py <the exact arguments recorded in the card>
magbench score --targets data/targets --predictions run/predictions.json --output models/<model_key>/scores.json
```

The runner usage and selection/property stages are documented in `benchmark_runner/README.md`. The reproduction command must use `magbench run` through the adapter, with unchanged benchmark defaults. Preserve the prediction JSON and the adjacent `phonons/` NPZ files. Archive the NPZ files with their relative paths matching `phonon_file` in the JSON. Only bounded ordinary NPZ files are accepted; archive links and paths outside the extraction folder are rejected.

Host the prediction JSON and either a phonon archive or the individual phonon files at stable public URLs. A directory manifest lists bounded `phonons/<name>.npz` paths; its directory URL addresses the corresponding NPZ files. Every listed file is verified and every phonon path used by the predictions must be listed. Record exact persisted byte sizes and SHA-256 digests. Limits are 32 MiB for prediction JSON, 128 MiB for the archive, 512 MiB expanded, at most 2048 archive members, and 64 MiB per NPZ file. Weights are probed with a range request and are not downloaded by validation.

## Validate locally

```sh
python scripts/check_cards.py
python scripts/validate_submission.py <model_key> --cache <large-storage-cache> --base-ref origin/dev --summary review.md
python -m pytest -q
python scripts/build_site.py
```

Online validation uses the exact dataset repository and immutable revision in `benchmark.json`; there is no fallback to an unpinned revision. Local datasets are verified against every pinned target size and SHA-256:

```sh
python scripts/validate_submission.py <model_key> --offline --data <dataset-root> --predictions <run/predictions.json> --summary review.md
```

Offline mode never claims public availability. For ordinary new submissions the public repository, checkpoint and artefact-download checks fail offline. For the owner-approved pending release entries, missing code or weights explicitly report `AWAITING ARTEFACTS`; known public addresses report `NOT RUN` when offline. Public prediction downloads also report `NOT RUN` when verified local predictions are supplied offline. Local validation checks the prediction JSON and every manifest-listed phonon file, target hashes, exchange route and the complete scorer replay. Missing local predictions fail replay for every entry.

## Pull request checks

Every push and pull request runs unit tests, all card/schema checks and the static site build. Model pull requests additionally run the validator from the trusted base revision with read-only permissions and no secrets. Submitted inference code is compiled and its declared adapter is checked with syntax-tree inspection; it is never imported or executed in this job.

The job checks the card, files and path guard; unauthenticated code and weight availability; both licences; bounded prediction downloads and SHA-256; pinned targets; the current versions and recorded exchange route; and a replay with the unchanged packaged scorer. All numerical fields of `scores.json` and all declared metrics must match the replay within 1e-9, and the integer ground-state pass count must match. Every check appears in a Markdown job summary. Any failed check fails the job; changes outside the model folder require maintainer review.

The initial data upload is in progress. The v0.2.3 remote revision is `to be provided` until the complete upload is verified. Online validation rejects this placeholder; local `--data` validation still checks every target size and SHA-256. The immutable remote revision must contain all target files matching the tracked manifest before online replay can pass. A maintainer must verify the complete v0.2.3 upload and update the revision in `benchmark.json`; partial uploads are rejected. Local validation uses the pinned target hashes in the meantime.

## Maintainer review

After reviewing the submission and after all public artefacts are available, activate it locally:

```sh
python scripts/ingest_model.py <model_key> --cache <large-storage-cache>
```

Ingest repeats strict public validation, sets `lifecycle: active`, and rebuilds the site payload. Owner-approved pending release records cannot be activated while artefacts or inference scripts are awaiting release. Prophet-Spin v1 has a usable wrapper around the vendored adapter; the other two inference scripts are explicit release placeholders. Listed entries can be activated only after strict public validation passes and their bounded metadata exceptions are removed.

Preview the static build with `python -m http.server` from `site/dist/`. The Pages workflow deploys only on a push to `main`; pull requests receive a site build artefact for review. No publication occurs during a local build.

## Prepare the GitHub Pages branch

The intended site address is https://kairosmaterial.github.io/Magbench/. All internal references are relative, including links from model pages. The build includes `.nojekyll` and works from a local file, a local HTTP server or the repository sub-path.

```sh
bash scripts/publish_pages.sh
```

This builds the site and prepares a local commit on the orphan `gh-pages` branch in a separate sibling worktree. It never pushes. Running it again refreshes a clean Pages worktree. The maintainer decides when to push this branch and configure branch-based Pages publishing; the Actions workflow remains available for deployment from `main` later.

## Architecture hyperparameters

Every card has a strict `hyperparams.architecture` block. Place `model_params` there; the previous top-level field is rejected. `cutoff_A` records the architecture's graph cutoffs in angstroms, preserving the model's list when it has several scales. The neighbour list may additionally expand to cover an explicit exchange term. `exchange_range_A` records the explicit exchange envelope or the longest representable spin-spin pair coupling. Use null only when the model has no such coupling, rather than when a separate range option is unset. State the direct envelope and density radius in `notes.architecture` for density-mediated models; pair couplings can extend to twice that radius. State the parameter-count convention in `notes.parameter_count`, including whether a separate moment head is counted.

The leaderboard places these values after the trailing Model group in every view. Cutoff lists retain their written order and sort by the largest cutoff. Hyperparameter values are not accuracy scores and receive no best-value emphasis.

## Completed owner entry

The public 6 Å entry has completed local replay and is active. Its inference code, weights, licences and prediction addresses are public; its corresponding author and benchmark-exposure declaration still require confirmation. The bounded `metadata_incomplete` owner policy pins its score and adapter and permits only these missing metadata fields. It never exempts public artefact checks for new submissions. Offline owner replay reports public availability as untested; strict public validation still requires the remote downloads and pinned data revision.

The trusted draft ingest path remains available for a prepared owner record: `python scripts/ingest_model.py <model_key> --predictions completed-run --data data`. It verifies bounds, hashes, targets, exchange route and the complete replay before listing the entry. Only a trusted preparation can request activation after local replay. A failed replay leaves tracked records unchanged.

## Dataset records

Run `python scripts/check_datasets.py` before model-card validation. Model submissions may add ordinary `datasets/<dataset_key>.yml` records, but may not edit records present in the trusted base commit. Other models remain protected; other changed paths require maintainer review. Dataset keys, parent references and model references must resolve, and parent cycles are rejected. Unknown subsets and unknown pretraining populations leave the total training-frame value unavailable. A full-dataset count is never assigned to a subset.

Dataset records omit unknown optional facts. Public release sizes describe the publisher release, not the amount consumed during model pretraining, so they do not produce a training-frame total. Magnetic metadata is required for new records. The existing OMat24, sAlex and ELEMENTA publisher records omit magnetic details that their checked documentation does not establish; only these three existing keys have that schema exception.

## Temporary site protection

With `MAGBENCH_SITE_PASSWORD` set, `scripts/publish_pages.sh` and the Pages workflow publish encrypted HTML and omit JSON; without it they publish the plain build.
The workflow reads this value from the repository secret of the same name, and the local command reads it only from its environment.
To remove protection, unset the local variable and remove the repository secret, then rebuild and publish.
Earlier plain builds remain in the branch history.

## Open decisions

- Record the approval history and detailed documentation of analytic effective pair readout, including density-mediated coefficients.
- Ratify the long-term versioning and archival process while retaining earlier rules and score records.
- Supply benchmark authors, affiliations and citation metadata.
- Confirm remaining model artefact addresses, metadata and the immutable data revision after the uploads are complete.
