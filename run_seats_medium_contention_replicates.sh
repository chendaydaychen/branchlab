#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source .venv-wsl/bin/activate
docker compose up -d
sleep 2
for seed in 1 2 3 4 5; do
  for mode in 2pl occ reuse_strict semantic_occ semantic_reuse; do
    python -m branchlab.seats_runner setup --flights 40 --customers 1000
    python -m branchlab.seats_runner run --mode "$mode" --winner-only --workers 8 --tasks 40 --candidates 4 --hot-flights 16 --seed "$seed"
  done
done
