#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM="$ROOT/external/tau2-bench"

cd "$UPSTREAM"
PYTHONPATH="$ROOT:$UPSTREAM/src" .venv/bin/python \
  "$ROOT/branchlab/tau3_matrix_runner.py" "$@"
