#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export PYTHONPATH="external/tau2-bench/src${PYTHONPATH:+:$PYTHONPATH}"
external/tau2-bench/.venv/bin/python -m pytest \
  tests/test_tau3_tx_environment.py \
  tests/test_semantic_contracts.py -q
python3 -m branchlab.semantic_contract_safety_replay
python3 -m branchlab.semantic_contract_binding_replay
python3 -m branchlab.semantic_contract_report

sha256sum \
  results/tau3_prefix_opportunity.json \
  results/tau3_tx_paired_replay.json \
  results/tau3_tx_paired_harmful.json \
  results/tau3_parallel_performance_comparison.json \
  results/semantic_differential_fuzz.json \
  results/semantic_contract_canary/summary.json \
  results/semantic_contract_safety_replay.json \
  results/semantic_contract_binding_replay.json \
  results/tau3_online_branch_branchlab_task40_b1_s960_contract_online.json \
  > results/final_evidence.sha256

echo "Offline validation complete; evidence hashes written to results/final_evidence.sha256"
