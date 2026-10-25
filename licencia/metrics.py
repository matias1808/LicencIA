from __future__ import annotations

from firebase_admin import firestore
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import streamlit as st

from .firebase import get_db
from .config import MIN_VALIDATED_EVENTS_FOR_METRICS


def record_prediction(actor_email: str, message: str, predicted_intent: str, confidence: float):
    _, ref = get_db().collection("nlp_events").add({
        "actor": actor_email,
        "message": message,
        "predicted_intent": predicted_intent,
        "validated_intent": None,
        "confidence": float(confidence),
        "source": "live",
        "baseline": False,
        "created_at": firestore.SERVER_TIMESTAMP,
        "validated_at": None,
    })
    return ref.id


def validate_event(event_id: str, validated_intent: str, validator: str):
    ref = get_db().collection("nlp_events").document(event_id)
    snap = ref.get()
    if snap.exists and (snap.to_dict() or {}).get("locked"):
        raise ValueError("Los registros base de validación están protegidos.")
    ref.update({
        "validated_intent": validated_intent,
        "validated_by": validator,
        "validated_at": firestore.SERVER_TIMESTAMP,
    })
    clear_metrics_cache()


def list_events(limit=600):
    q = get_db().collection("nlp_events").order_by(
        "created_at", direction=firestore.Query.DESCENDING
    ).limit(limit)
    out = []
    for d in q.stream():
        x = d.to_dict() or {}
        x["id"] = d.id
        out.append(x)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _validated_rows_cached():
    return [x for x in list_events(2000) if x.get("validated_intent")]


def clear_metrics_cache():
    try:
        _validated_rows_cached.clear()
    except Exception:
        pass


def _compute_from_rows(rows):
    if len(rows) < MIN_VALIDATED_EVENTS_FOR_METRICS:
        return None, rows
    y_true = [x["validated_intent"] for x in rows]
    y_pred = [x["predicted_intent"] for x in rows]
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "count": len(rows),
        "baseline_count": sum(1 for x in rows if x.get("baseline")),
    }
    return (metrics, None), rows


def compute_metrics():
    return _compute_from_rows(_validated_rows_cached())


def compute_baseline_metrics():
    rows = [x for x in _validated_rows_cached() if x.get("baseline")]
    return _compute_from_rows(rows)
