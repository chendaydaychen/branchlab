# Semantic-contract DeepSeek canary

| task | schema | operation | hard P | hard R | auth R | raw omissions | static guard gaps | after hardening |
|---|---:|---:|---:|---:|---:|---|---|---|
| 12 | 1 | 1 | 0.667 | 1.000 | 1.000 | - | - | - |
| 15 | 1 | 1 | 0.692 | 1.000 | 1.000 | - | - | - |
| 20 | 1 | 1 | 1.000 | 1.000 | 1.000 | - | - | - |
| 39 | 1 | 1 | 1.000 | 0.833 | 1.000 | refund_destination_unchanged | refund_destination_unchanged | - |
| 40 | 1 | 1 | 1.000 | 0.750 | 1.000 | reservation_active | reservation_active | - |

- Schema-valid rate: 1.000
- Exact-operation rate: 1.000
- Mean hard-predicate recall: 0.9166666666666666
- Tasks with dangerous omissions: 2
- Tasks caught by static guard: 2
- Tasks with omissions after hardening: 0
- Provider usage: {'prompt_tokens': 24770, 'completion_tokens': 1859, 'total_tokens': 26629}

This three-task run is a canary, not a paper-level aggregate result.
