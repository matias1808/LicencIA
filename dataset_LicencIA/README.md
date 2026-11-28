# LicencIA Dataset

This dataset contains **224 labeled requests in Spanish** related to Microsoft 365 technology license management. The requests are synthetic examples generated for evaluating intent classification in the LicencIA project.

The dataset includes license assignment, removal, reassignment, inventory queries, user-license consultations, auditing, and other conversational intents.

## Files

- **`validation_224_synthetic.csv`** — the 224 labeled requests.
- **`reproduce_metrics.py`** — script to evaluate the requests using the LicencIA classifier.

## Dataset structure

| Column | Description |
| --- | --- |
| `sample_id` | Unique identifier for each request. |
| `request_text` | Request written in Spanish. |
| `intent_label` | Expected classification of the request. |
| `source_function` | Function used to generate the example. |

**Purpose:** To support the evaluation of natural language understanding and intent classification for technology license management.
