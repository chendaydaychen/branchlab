# External sources for reproduction

The `external/` and `vendor/` directories are independent upstream checkouts and
are intentionally not included in this repository. Clone the sources below at
the recorded revisions before running experiments. Do not commit their nested
`.git` directories or downloaded datasets into this repository.

| Local directory | Upstream | Revision |
|---|---|---|
| `external/tau-bench` | https://github.com/sierra-research/tau-bench.git | `59a200c6d575d595120f1cb70fea53cef0632f6b` |
| `external/tau2-bench` | https://github.com/sierra-research/tau2-bench.git | `b7ea9074c1cba482b30687fecdb5c8425fd6f619` |
| `vendor/benchbase` | https://github.com/cmu-db/benchbase.git | `33c00473807ebd49304d114a6d769d2d2b2bbb34` |
| `vendor/BIRD-Interact` | https://github.com/bird-bench/BIRD-Interact.git | `451fe2c3518ee1cf908d8139e2913483bd519381` |
| `vendor/bird-interact-lite` | https://huggingface.co/datasets/birdsql/bird-interact-lite | `f7881a9c2b9630cc4fc13b0c39279740b0a2fd87` |

For example, in WSL:

```bash
git clone https://github.com/sierra-research/tau2-bench.git external/tau2-bench
git -C external/tau2-bench checkout b7ea9074c1cba482b30687fecdb5c8425fd6f619
```

Install its Python dependencies in a local, ignored virtual environment as
described in the upstream repository and the experiment protocols. The
`run_final_offline_validation.sh` script currently expects that environment at
`external/tau2-bench/.venv/`.

**Local checkout caveat:** `vendor/BIRD-Interact/env/docker-compose.yml` has an
uncommitted local modification at the time this manifest was written. It is
not part of the recorded upstream revision or this repository. Experiments
depending on it must document and reproduce that change separately.

The repository includes curated raw experiment JSON, summaries and figures in
`results/` and `figures/`. Machine-specific logs under `results/matrix_logs/`
are ignored. Do not commit real API keys; `.env.example` contains placeholders
only. The `branchlab` PostgreSQL credential in the sample Docker setup is a
local development credential, not suitable for deployment.
