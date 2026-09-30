# Semantic differential fuzzing

Seed: 20260922. Trials per workload: 100000. The oracle is an independent executable task specification. This is a model-level state/schedule test; database crash and process-failure injection are evaluated separately.

| workload | controller | false accepts | false rejects |
|---|---|---:|---:|
| seats | Semantic validation | 0 | 0 |
| seats | Strict version validation | 0 | 58035 |
| seats | RC blind materialization model | 32573 | 0 |
| tatp | Semantic validation | 0 | 0 |
| tatp | Strict version validation | 0 | 16755 |
| tatp | RC blind materialization model | 11896 | 0 |
