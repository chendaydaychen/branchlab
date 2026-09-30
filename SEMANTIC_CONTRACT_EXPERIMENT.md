# LLM semantic-contract experiment (budget-capped)

## Goal

Measure whether an LLM can compile user-visible task context and public airline
policy into a machine-checkable contract. The LLM never decides commit. Its JSON
is schema-checked and the deterministic validator remains the trusted component.

## Zero-cost preparation

```bash
cd /mnt/z/at/branchlab
python3 -m branchlab.semantic_contract_trace_extract
python3 -m branchlab.semantic_contract_experiment
python3 -m pytest tests/test_semantic_contracts.py -q
```

The extractor uses the first recorded trial for each canary and stops immediately
before its first target write. System prompts and hidden benchmark intent are not
included. The experiment command is a dry run. It creates `results/semantic_contract_canary/plan.json`
and makes no network request.

## Small canary

Only after reviewing the plan and configuring the WSL secret:

```bash
python3 -m branchlab.semantic_contract_experiment \
  --task-ids 12 39 40 \
  --execute \
  --max-api-calls 3
python3 -m branchlab.semantic_contract_report
```

The program has a hard cap of three API calls and 1,000 output tokens per call.
It checkpoints each task immediately and will not pay to regenerate an existing
result. Initial reporting must separate schema validity, hard-predicate recall,
dangerous omissions, and exact operation accuracy.

## Expansion gate

Do not expand beyond the canary until all three outputs are schema-valid and
dangerous omissions have been manually reviewed. A larger run must use a separate
entry point and a newly approved budget; this canary intentionally cannot be
turned into a batch run by changing command-line arguments.

## Completed five-operation canary

The capped study now contains one recorded pre-write trace for each airline
mutation family: baggage update (task 12), flight update (task 15), booking
(task 20), cancellation (task 39), and passenger update (task 40).

- API calls: 5 total, executed as batches of 3 and 2.
- Provider-reported usage: 24,770 prompt tokens, 1,859 completion tokens,
  26,629 total tokens.
- Schema-valid contracts: 5/5.
- Exact target operation: 5/5.
- Mean hard-predicate precision: 0.872.
- Mean hard-predicate recall: 0.917.
- Mean authorization recall: 1.000.
- Raw contracts with a dangerous omission: 2/5.
- Omissions caught by the trusted operation template: 2/2.
- Gold dangerous omissions after hardening: 0/5.

These results support a hybrid compiler, not direct LLM authorization. The LLM
proposes task-specific clauses; a trusted template supplies the non-removable
operation-level minimum; a deterministic validator decides commit.

Two additional offline checks are complete:

- `results/semantic_contract_safety_replay.md`: 38/38 single-predicate omissions
  detected and restored across the five gold contracts.
- `results/semantic_contract_binding_replay.md`: 5/5 exact writes accepted, while
  wrong-branch, wrong-snapshot, and changed-write replays were rejected 5/5.

The transaction environment now exposes a compiled-contract gate and records
`contract_compilations`, `contract_checks`, and `contract_rejections`. This gate binds a hardened contract
to a branch id, initial snapshot id, operation, and canonical write arguments.
The existing operation-specific state validator still performs the actual data
predicate checks.

## Saved-contract online runner canary

The online BranchLab runner now accepts `--saved-contract`. It loads the saved
LLM output for the task, validates its schema, hardens it with the trusted
operation template, and automatically binds it to the continuation branch,
initial snapshot, operation, and canonical arguments on the first write.

One deliberately small live canary was run for tau3 Airline task 40 with one
candidate, temperature 0, and base seed 950:

- Reward: 1.0.
- Database final-state match: true.
- Contract compilations/checks/rejections: 1/1/0.
- Transaction validation failures: 0.
- Semantic rebases: 1.
- Physical reads: one in the shared prefix and zero in the continuation.
- End-to-end wall clock: 13.95 seconds.
- Actual cost including the fork probe: USD 0.002700828.

This run proves end-to-end executability of the saved-contract path. It has one
candidate, so it provides no evidence of cross-branch speedup; the fork probe
also makes it slightly more expensive than the independent single-candidate
estimate. Performance claims must continue to use multi-candidate experiments.

## Online-generated-contract end-to-end canary

The final integration gap was closed with a single budget-capped run. At the
first write intent, the runner sanitized the public trajectory context, issued
exactly one DeepSeek contract-generation call, parsed and hardened the result,
bound it to the branch/snapshot/write arguments, and checked it before allowing
the database mutation.

- Workload: tau3 Airline task 40; one candidate; base seed 960.
- Task reward: 1.0; database final-state match: true.
- Contract-generation usage: 2,657 prompt + 227 completion = 2,884 tokens.
- Contract-generation latency: 1.37 seconds.
- Contract compilations/checks/rejections: 1/1/0.
- Transaction validation failures: 0; semantic rebases: 1.
- End-to-end wall clock: 14.21 seconds.
- Agent/user/probe LiteLLM cost: USD 0.002993568; the direct contract call is
  reported by tokens because that client does not expose a comparable cost field.

This closes the functional online path. It is intentionally a one-sample canary,
not a performance or LLM-quality aggregate. No further API calls are required for
the completed experiment package; the five-operation quality study and all
safety/binding tests replay saved artifacts offline.
