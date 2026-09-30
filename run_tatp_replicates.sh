#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source .venv-wsl/bin/activate
docker compose up -d
sleep 2
for seed in 1 2 3 4 5; do
  for mode in 2pl occ reuse_strict semantic_occ semantic_reuse; do
    python -m branchlab.tatp_runner setup --subscribers 100
    python -m branchlab.tatp_runner run --mode "$mode" --winner-only --workers 8 --tasks 20 --candidates 4 --hot-subscribers 1 --seed "$seed"
  done
done
