## Model submission

Model key:

- [ ] Only my own `models/<model_key>/` is added or changed; any needed dataset records are new files under `datasets/`, and existing dataset records are unchanged.
- [ ] The strict model card uses `lifecycle: pending` and includes one corresponding author.
- [ ] Public open-source inference code and publicly downloadable evaluated weights are linked; both licences are stated.
- [ ] The adapter, exact reproduction command, Python version and pinned dependencies are included.
- [ ] Prediction JSON and a phonon archive or per-file phonon manifest are hosted externally with exact sizes and SHA-256 digests.
- [ ] `scores.json` comes from the unchanged packaged scorer and agrees with the declared metrics.
- [ ] Protocol, data and runner versions are current; the recorded exchange route agrees with the card.
- [ ] I declared use of benchmark materials or scores in training, validation and selection in `test_set_informed` and, when true, a one-sentence `notes.disclosure`.
- [ ] Every training-set reference resolves to a dataset record; subset usage and architecture hyperparameters are stated.
- [ ] I ran `python scripts/validate_submission.py <model_key> --offline --data data --predictions run/predictions.json` and attached the result.
