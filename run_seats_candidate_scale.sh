#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
candidate_count="${1:?candidate count required}"
source .venv-wsl/bin/activate
for seed in 1 2 3 4 5; do
  for mode in 2pl occ reuse_strict semantic_occ semantic_reuse; do
    result_file="results/seats_${mode}_w8_c${candidate_count}_h40_s${seed}_candidate_scale.json"
    if [[ -f "$result_file" ]]; then
      continue
    fi
    docker compose up -d >/dev/null
    docker compose restart postgres >/dev/null
    python -m branchlab.seats_runner setup --flights 40 --customers 1000
    python -m branchlab.seats_runner run --mode "$mode" --winner-only --workers 8 --tasks 40 --candidates "$candidate_count" --hot-flights 40 --discovery-ms 20 --think-ms 10 --seed "$seed" --result-tag candidate_scale
  done
done
