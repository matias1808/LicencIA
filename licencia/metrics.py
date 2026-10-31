from __future__ import annotations

from firebase_admin import firestore
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import streamlit as st

from .firebase import get_db
from .config import MIN_VALIDATED_EVENTS_FOR_METRICS


BASELINE_SOURCE = "validation_baseline_v2"


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
    # Una predicción nueva todavía no cambia las métricas, pero limpiamos el cache
    # para que la cola de validación y los contadores siempre reflejen Firebase.
    clear_metrics_cache()
    return ref.id


def validate_event(event_id: str, validated_intent: str, validator: str):
    ref = get_db().collection("nlp_events").document(event_id)
    snap = ref.get()
    if not snap.exists:
        raise ValueError("La predicción ya no existe en Firebase.")

    current = snap.to_dict() or {}
    if current.get("locked"):
        raise ValueError("Los registros base de validación están protegidos.")

    ref.update({
        "validated_intent": validated_intent,
        "validated_by": validator,
        "validated_at": firestore.SERVER_TIMESTAMP,
    })
    # Fundamental: la nueva validación debe aparecer inmediatamente en la
    # comparación Base vs. Estado actual.
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


def _is_baseline(row: dict) -> bool:
    """Reconoce el baseline histórico aunque provenga de versiones anteriores."""
    return bool(row.get("baseline")) or row.get("source") == BASELINE_SOURCE


@st.cache_data(ttl=60, show_spinner=False)
def _validated_rows_cached():
    """
    Lee TODAS las validaciones humanas persistidas en Firebase.

    Antes se partía de una lista limitada. Para la evolución del modelo no se
    debe truncar el histórico: cada registro con validated_intent cuenta en el
    estado actual, mientras que los 178 registros baseline permanecen como
    referencia congelada.
    """
    out = []
    for d in get_db().collection("nlp_events").stream():
        x = d.to_dict() or {}
        if not x.get("validated_intent"):
            continue
        x["id"] = d.id
        x["baseline"] = _is_baseline(x)
        out.append(x)
    return out


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
        "baseline_count": sum(1 for x in rows if _is_baseline(x)),
    }
    return (metrics, None), rows


def compute_metrics():
    """Métricas actuales = baseline + todas las validaciones posteriores."""
    return _compute_from_rows(_validated_rows_cached())


def compute_baseline_metrics():
    """Referencia inicial congelada = solo registros marcados como baseline."""
    rows = [x for x in _validated_rows_cached() if _is_baseline(x)]
    return _compute_from_rows(rows)
