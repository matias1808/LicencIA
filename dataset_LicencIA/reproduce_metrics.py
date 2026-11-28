#!/usr/bin/env python3
"""Re-evaluate the public, synthetic LicencIA sample against the current parser.

Usage (from the LicencIA repository root):
    python dataset_LicencIA/reproduce_metrics.py

No Firestore reads or writes are performed: the licensing catalog is loaded
from the local synthetic seed_licenses.csv file and injected into the parser.

This script is not a reproduction of the manuscript's separate nine-model
training benchmark.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = Path(__file__).with_name("validation_224_synthetic.csv")
CATALOG_PATH = REPO_ROOT / "data" / "seed_licenses.csv"
sys.path.insert(0, str(REPO_ROOT))

from licencia import nlp  # noqa: E402


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    samples = read_csv_rows(DATASET_PATH)
    if len(samples) != 224:
        raise RuntimeError(f"Expected 224 samples, found {len(samples)}.")

    catalog_rows = read_csv_rows(CATALOG_PATH)
    catalog = [
        {
            "id": item["license_id"],
            "name": item["name"],
            "sku": item["sku"],
            "group_name": "",
        }
        for item in catalog_rows
    ]

    # The real parser uses a cached Firestore-backed license catalog.
    # Override only this lookup so dataset evaluation is fully offline.
    nlp._cached_licenses = lambda: catalog

    expected = [row["intent_label"] for row in samples]
    predicted = [nlp.parse_message(row["request_text"]).intent for row in samples]

    print("Dataset: 224 synthetically generated LicencIA requests")
    print("Intent distribution:", dict(sorted(Counter(expected).items())))
    print("Parser version: current local intent_model_v4.joblib + current NLP rules")
    print("Catalog: local synthetic data/seed_licenses.csv (offline)")
    print()
    print(f"Accuracy:           {accuracy_score(expected, predicted) * 100:.2f}%")
    print(
        f"Weighted precision: {precision_score(expected, predicted, average='weighted', zero_division=0) * 100:.2f}%"
    )
    print(
        f"Weighted recall:    {recall_score(expected, predicted, average='weighted', zero_division=0) * 100:.2f}%"
    )
    print(
        f"Weighted F1:        {f1_score(expected, predicted, average='weighted', zero_division=0) * 100:.2f}%"
    )
    print(
        f"Macro F1:           {f1_score(expected, predicted, average='macro', zero_division=0) * 100:.2f}%"
    )
    print()
    print(classification_report(expected, predicted, zero_division=0))
    print(
        "Note: this describes the current local parser on a synthetic sample. "
        "It is not an independent real-world validation or a reproduction "
        "of the separate nine-algorithm benchmark."
    )


if __name__ == "__main__":
    main()
