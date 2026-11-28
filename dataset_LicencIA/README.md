# dataset_LicencIA

**A transparent, labeled Spanish-language dataset for the LicencIA technology-license request classification project.**

LicencIA investigates how natural language processing (NLP), machine learning (ML), entity interpretation, and deterministic business rules can support Microsoft 365 license-management requests.

## Dataset files

| File | Description |
| --- | --- |
| [validation_224_synthetic.csv](validation_224_synthetic.csv) | 224 Spanish-language, synthetically generated requests with their intended intent labels and the source function used to generate each record. |
| [reproduce_metrics.py](reproduce_metrics.py) | Optional, read-only evaluation script that applies the **current LicencIA parser** to each published request and prints classification metrics. |

**Language:** Spanish (request text).  
**Records:** 224.  
**Task:** Multiclass intent classification.  
**Format:** UTF-8 CSV.  
**Scope:** Technology licensing, Microsoft 365 services, inventory inquiries, and basic conversational routing.

### CSV schema

| Column | Definition |
| --- | --- |
| `sample_id` | Dataset-local sequential identifier, 001–224. |
| `request_text` | The Spanish-language input message. |
| `intent_label` | Intended intent category assigned by the dataset generator. |
| `source_function` | Provenance: the corresponding sample-generation function in `licencia/metric_seed.py`. **This is not a train/test split.** |

### Intent categories

`assign`, `unassign`, `reassign`, `inventory`, `user_licenses`, `license_holders`, `audit`, `catalog`, `capabilities`, `greeting`, `wellbeing`, `thanks`, `farewell`, and `out_of_scope`.

## Data provenance — important for scientific use

The 224 requests in this folder were **programmatically generated**, rather than obtained from an independently collected sample of live production requests. They were reconstructed **without changing their text or labels** from the existing source functions [`baseline_samples()` and `current_comparison_samples()`](../licencia/metric_seed.py). The source code uses illustrative email addresses and product names to create test messages.

These examples should therefore be described as a **synthetic, script-generated validation or demonstration set**. They must **not** be presented as 224 independently gathered, human-annotated, real-world requests. The data generator was also designed with intended model outcomes in mind, so this sample is not an unbiased holdout for estimating generalization.

The CSV contains **expected labels, not recorded model predictions**. It is **not** a raw export of the Firestore `nlp_events` collection. The published CSV alone does not independently establish the paper's accumulated classification metrics (accuracy 98.21%, precision 98.43%, recall 98.21%, F1 98.24%) or the reported nine-algorithm benchmark. Those claims require their original per-record predictions and evaluation artifacts.

## Related training and validation resources

Other data files maintained in the parent LicencIA repository include:

- [`data/beto_training_v5.csv`](../data/beto_training_v5.csv) — separate Transformer-oriented training material.
- [`data/beto_validation_v5.csv`](../data/beto_validation_v5.csv) — separate validation material.
- [`data/nlp_training_v4.csv`](../data/nlp_training_v4.csv) — separate intent-classification training material.
- [`data/nlp_challenge_v3.csv`](../data/nlp_challenge_v3.csv) — separate challenge/evaluation examples.

These files are **not interchangeable** with the 224 records and should not be assumed to constitute the complete evaluation protocol for all nine algorithms.

## How to reproduce parser predictions

From the root of the LicencIA repository, install its documented Python dependencies and run:

```bash
python dataset_LicencIA/reproduce_metrics.py
```

The script reads the CSV, invokes `licencia.nlp.parse_message` for each row, and reports accuracy, weighted precision, weighted recall, weighted F1, macro F1, and the complete classification report. It does **not** access or modify Firestore.

**Note:** This reproduces the behavior of the parser and model available in the checked-out repository at run time; it does not reproduce the independent nine-model training experiment. Scores may change when model files, dependencies, or parsing rules change.

## Additional artifacts needed for journal-level verification

To reproduce the **paper's published numerical results**, the authors should additionally provide, subject to privacy and authorization constraints:

1. The exact evaluation split(s), expected labels, and per-record model predictions for every reported metric.
2. Model checkpoint/version identifiers, preprocessing code, hyperparameters, and training logs.
3. Class distributions and, where relevant, fold-level results for every compared algorithm.
4. An explanation of which evaluation produced each reported result, keeping the platform's accumulated monitoring distinct from the comparative benchmark.

When publishing any further material, remove or replace personal or confidential information and verify that the data can lawfully be shared.

## Citation and intended use

Please cite the LicencIA manuscript together with the repository URL and the commit or release used to retrieve this dataset. The dataset is supplied for **transparent inspection of the existing synthetic request examples**, educational analysis, and reproducibility of this particular sample-generation procedure, **not** as proof of production performance.

**Repository:** https://github.com/matias1808/LicencIA/tree/main/dataset_LicencIA
