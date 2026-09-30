#!/usr/bin/env bash
set -euo pipefail

# Run from WSL. The API key is accepted from the process environment or from a
# private file outside the repository; it never enters this repository or a
# command argument.
SECRET_FILE="${TAU3_SECRET_FILE:-${HOME}/.config/branchlab/deepseek_api_key}"
if [[ -z "${DEEPSEEK_API_KEY:-}" && -f "${SECRET_FILE}" ]]; then
  if [[ "$(stat -c '%a' "${SECRET_FILE}")" != "600" ]]; then
    echo "Refusing to read ${SECRET_FILE}: permissions must be 600." >&2
    exit 2
  fi
  IFS= read -r DEEPSEEK_API_KEY < "${SECRET_FILE}"
  export DEEPSEEK_API_KEY
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DEEPSEEK_API_KEY is not set." >&2
  echo "Set it in the environment, or create the private file ${SECRET_FILE} with mode 600." >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAU_DIR="${ROOT_DIR}/external/tau2-bench"
MODEL="${TAU3_MODEL:-deepseek/deepseek-flash}"
PHASE="${1:-smoke}"
UV_BIN="${TAU3_UV_BIN:-$(command -v uv || true)}"
if [[ -z "${UV_BIN}" && -x "${HOME}/.local/bin/uv" ]]; then
  UV_BIN="${HOME}/.local/bin/uv"
fi
if [[ -z "${UV_BIN}" ]]; then
  echo "uv was not found; set TAU3_UV_BIN to its absolute path." >&2
  exit 2
fi

case "${PHASE}" in
  smoke)
    TASK_IDS=(7)
    TRIALS=1
    CONCURRENCY=1
    SAVE_TO="branchlab_deepseek_smoke"
    ;;
  pilot)
    TASK_IDS=(7 11 12 14 15)
    TRIALS=1
    CONCURRENCY=1
    SAVE_TO="branchlab_deepseek_pilot"
    ;;
  mutating)
    # All mutation-bearing tasks in the pinned airline/base task set.
    TASK_IDS=(7 11 12 14 15 17 20 21 23 33 39 40 42 8 16 18 19 22 24 25 29 30 32 35 37 44)
    TRIALS="${TAU3_TRIALS:-3}"
    CONCURRENCY="${TAU3_CONCURRENCY:-3}"
    SAVE_TO="branchlab_deepseek_mutating"
    ;;
  *)
    echo "Usage: $0 {smoke|pilot|mutating}" >&2
    exit 2
    ;;
esac

cd "${TAU_DIR}"

# Fail locally before making a paid request if the provider/model string cannot
# be resolved by the exact LiteLLM installation pinned in this environment.
TAU3_MODEL="${MODEL}" "${UV_BIN}" run python - <<'PY'
import os
from litellm.utils import get_llm_provider

model = os.environ["TAU3_MODEL"]
resolved_model, provider, _, _ = get_llm_provider(model)
if provider != "deepseek":
    raise SystemExit(f"Expected DeepSeek provider, got {provider!r}")
print(f"Resolved {model} -> provider={provider}, model={resolved_model}")
PY

echo "Running tau3 phase=${PHASE}, model=${MODEL}, tasks=${#TASK_IDS[@]}, trials=${TRIALS}"
"${UV_BIN}" run tau2 run \
  --domain airline \
  --task-set-name airline \
  --task-split-name base \
  --agent llm_agent \
  --agent-llm "${MODEL}" \
  --agent-llm-args '{"temperature": 0.0}' \
  --user user_simulator \
  --user-llm "${MODEL}" \
  --user-llm-args '{"temperature": 0.0}' \
  --task-ids "${TASK_IDS[@]}" \
  --num-trials "${TRIALS}" \
  --max-concurrency "${CONCURRENCY}" \
  --max-steps 100 \
  --timeout 900 \
  --max-retries 3 \
  --retry-delay 2 \
  --seed 300 \
  --save-to "${SAVE_TO}" \
  --auto-resume \
  --verbose-logs \
  --llm-log-mode all

echo "Results: ${TAU_DIR}/data/simulations/${SAVE_TO}/results.json"
