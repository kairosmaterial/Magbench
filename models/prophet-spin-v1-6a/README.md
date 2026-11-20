# Prophet-Spin v1 (6 Å)

This entry evaluates the public six-layer checkpoint, separately from the ten-layer Prophet-Spin v1 entry. The card records the evaluated environment, public source revision, weight hashes and prediction manifest.

```sh
git clone https://github.com/kairosmaterial/prophet prophet
git -C prophet checkout 62bc2769fa83214fd564c7df263ee254e73fc6e9
curl -fL https://huggingface.co/kairosmaterial/prophet/resolve/main/prophet-v1-mag.pt -o prophet-v1-mag.pt
curl -fL https://huggingface.co/kairosmaterial/prophet/resolve/main/prophet-v1-mag-head.pt -o prophet-v1-mag-head.pt
```

Verify file sizes and SHA-256 values against the card before inference. Download weights directly to suitable storage. Run `inference.command` from the benchmark repository with `data/inputs` and `data/targets` available. The adapter uses public inference code, retains lattice shifts and sums the directed half-bond contributions for periodic exchange readout. The shared runner and scorer are unchanged.

Re-score the downloaded predictions locally:

```sh
python scripts/validate_submission.py prophet-spin-v1-6a --offline --data data --predictions completed-run/predictions.json
```

The numerical evaluation is complete. The corresponding author and benchmark-exposure declaration remain unconfirmed. Offline validation checks the predictions and replay; it does not establish remote availability.
