#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

source .venv-wsl/bin/activate

wait_for_postgres() {
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if docker compose exec -T postgres pg_isready -U branchlab -d branchlab >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

for hot_flights in 1 40; do
  for workers in 8 32; do
    for seed in 1 2 3 4 5; do
      for mode in pg_rc pg_rr pg_ssi; do
        result_file="results/seats_${mode}_w${workers}_c4_h${hot_flights}_s${seed}_native_baseline.json"
        if [[ -f "$result_file" ]]; then
          continue
        fi
        completed=false
        for attempt in 1 2 3; do
          docker compose down --remove-orphans >/dev/null 2>&1 || true
          if docker compose up -d >/dev/null \
            && wait_for_postgres \
            && python -m branchlab.seats_runner setup --flights 40 --customers 1000 \
            && python -m branchlab.seats_runner run \
              --mode "$mode" \
              --winner-only \
              --workers "$workers" \
              --tasks 40 \
              --candidates 4 \
              --hot-flights "$hot_flights" \
              --discovery-ms 20 \
              --think-ms 10 \
              --seed "$seed" \
              --result-tag native_baseline; then
            completed=true
            break
          fi
          echo "retrying mode=$mode workers=$workers h=$hot_flights seed=$seed attempt=$attempt" >&2
        done
        if [[ "$completed" != true ]]; then
          echo "experiment failed after three attempts: mode=$mode workers=$workers h=$hot_flights seed=$seed" >&2
          exit 1
        fi
      done
    done
  done
done
