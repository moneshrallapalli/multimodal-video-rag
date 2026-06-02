# eval

Offline evaluation harness. Holds the hand-verified golden dataset
(`golden/`) and the scripts that run the retrieval ablation (dense -> hybrid
-> +rerank -> +query-rewrite), the custom retrieval metrics (Recall@K, MRR,
timestamp accuracy, modality accuracy, no-answer accuracy), and RAGAS. Outputs
a results JSON that the web dashboard renders.
