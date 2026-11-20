# Prophet-Spin v1 (6 Å)

This draft is excluded from the site until a complete prediction set is replayed. It uses the public six-layer checkpoint, separately from the existing ten-layer Prophet-Spin v1 entry.

Use a dedicated inference environment with the dependencies in the card. The preparation environment is recorded provisionally; confirm it against the completed evaluation receipt.

```sh
git clone https://github.com/kairosmaterial/prophet prophet
git -C prophet checkout 62bc2769fa83214fd564c7df263ee254e73fc6e9
curl -fL https://huggingface.co/kairosmaterial/prophet/resolve/main/prophet-v1-mag.pt -o prophet-v1-mag.pt
curl -fL https://huggingface.co/kairosmaterial/prophet/resolve/main/prophet-v1-mag-head.pt -o prophet-v1-mag-head.pt
```

Verify both file sizes and SHA-256 values against the card before inference. Download weights directly to a suitable storage location. Run the exact `inference.command` in the card from the benchmark repository, with `data/inputs` and `data/targets` available. The script loads the public runtime, uses the packaged adapter for moment initialisation and EFS, and reads periodic exchange bonds with the public six-argument exchange-head convention. It retains lattice shifts and sums the two directed half-bond contributions. The runner and scorer are unchanged.

Once a completed folder contains `predictions.json`, adjacent `phonons/` files and `scores.json`, prepare this owner-approved entry locally:

```sh
python scripts/ingest_model.py prophet-spin-v1-6a --predictions completed-run --data data
```

Ingest verifies the targets and every prediction file, repeats scoring, and requires the complete fixed-cohort score record to agree within 1e-9. It writes the card and canonical scores, changes the entry to pending and rebuilds the payload. Raw predictions remain outside the repository. Missing public prediction URLs and remaining author/training metadata read “to be provided”; this local preparation does not claim public artefact validation or activate the entry. Ordinary submissions continue to require strict public validation.
