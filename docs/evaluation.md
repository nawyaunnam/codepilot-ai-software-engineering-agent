# Evaluation

Maintain golden questions covering symbol location, request flow, dependency impact, bug localization, and required feature files. Measure citation recall and precision, faithfulness, unsupported-claim rate, retrieval MRR, plan file recall, patch application rate, test pass rate, mutation score, latency, and token cost.

Hallucination tests should remove relevant files, insert conflicting names, rename symbols, add generated code, and ask unanswerable questions. A correct system abstains when evidence is absent. Patch evaluation runs on disposable snapshots and verifies unrelated tests and formatting remain unchanged.
