# Adversarial / evasion awareness (checklist)

Flow-ML IDS can be evaded by **crafting** traffic statistics to mimic benign baselines.

- **Sanity:** run [`scripts/perturbation_sanity.py`](../scripts/perturbation_sanity.py) on validation data to see **prediction flip rate** under small Gaussian feature noise.
- **Do not** treat low flip rate as “secure”; it is a coarse robustness smell test only.
- **Combine** with rate limits, allowlists, and non-ML controls for anything safety-critical.
