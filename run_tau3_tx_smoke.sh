#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAU_DIR="${ROOT_DIR}/external/tau2-bench"
PYTHON_BIN="${TAU_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "tau3 virtual environment is missing: ${PYTHON_BIN}" >&2
  exit 2
fi

export PYTHONPATH="${ROOT_DIR}:${TAU_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
for mode in 2pl occ branchlab; do
  echo "Running transaction-aware tau3 smoke: ${mode}"
  "${PYTHON_BIN}" -m branchlab.tau3_tx_smoke \
    --mode "${mode}" \
    --task-id "${TAU3_TASK_ID:-11}" \
    --model "${TAU3_MODEL:-deepseek/deepseek-flash}" \
    --seed "${TAU3_SEED:-300}"
done
