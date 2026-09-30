#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

hot_flights="${1:?hot-flight count required}"
source .venv-wsl/bin/activate

for workers in 1 4 8 16 32; do
  for seed in 1 2 3 4 5; do
    for mode in 2pl occ reuse_strict semantic_occ semantic_reuse; do
      result_file="results/seats_${mode}_w${workers}_c4_h${hot_flights}_s${seed}_worker_scale.json"
      if [[ -f "$result_file" ]]; then
        continue
      fi
      docker compose up -d >/dev/null
      docker compose restart postgres >/dev/null
      python -m branchlab.seats_runner setup --flights 40 --customers 1000
      python -m branchlab.seats_runner run \
        --mode "$mode" \
        --winner-only \
        --workers "$workers" \
        --tasks 40 \
        --candidates 4 \
        --hot-flights "$hot_flights" \
        --discovery-ms 20 \
        --think-ms 10 \
        --seed "$seed" \
        --result-tag worker_scale
    done
  done
done
