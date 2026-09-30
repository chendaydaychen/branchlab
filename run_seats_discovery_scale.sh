#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

discovery_ms="${1:?discovery cost in milliseconds required}"
source .venv-wsl/bin/activate

for seed in 1 2 3 4 5; do
  for mode in 2pl occ reuse_strict semantic_occ semantic_reuse; do
    result_file="results/seats_${mode}_w8_c4_h40_s${seed}_discovery_${discovery_ms}ms.json"
    if [[ -f "$result_file" ]]; then
      continue
    fi
    docker compose up -d >/dev/null
    docker compose restart postgres >/dev/null
    python -m branchlab.seats_runner setup --flights 40 --customers 1000
    python -m branchlab.seats_runner run \
      --mode "$mode" \
      --winner-only \
      --workers 8 \
      --tasks 40 \
      --candidates 4 \
      --hot-flights 40 \
      --discovery-ms "$discovery_ms" \
      --think-ms 10 \
      --seed "$seed" \
      --result-tag "discovery_${discovery_ms}ms"
  done
done
