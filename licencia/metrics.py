\
from __future__ import annotations

from firebase_admin import firestore
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import pandas as pd

from .firebase import get_db
from .config import MIN_VALIDATED_EVENTS_FOR_METRICS


def record_prediction(actor_email: str, message: str, predicted_intent: str, confidence: float):
  _, ref = get_db().collection("nlp_events").add({
    "actor": actor_email,
    "message": message,
    "predicted_intent": predicted_intent,
    "validated_intent": None,
    "confidence": float(confidence),
    "created_at": firestore.SERVER_TIMESTAMP,
    "validated_at": None,
  })
  return ref.id


def validate_event(event_id: str, validated_intent: str, validator: str):
  get_db().collection("nlp_events").document(event_id).update({
    "validated_intent": validated_intent,
    "validated_by": validator,
    "validated_at": firestore.SERVER_TIMESTAMP,
  })


def list_events(limit=300):
  q = get_db().collection("nlp_events").order_by(
    "created_at", direction=firestore.Query.DESCENDING
  ).limit(limit)
  out = []
  for d in q.stream():
    x = d.to_dict()
    x["id"] = d.id
    out.append(x)
  return out


def compute_metrics():
  rows = [x for x in list_events(2000) if x.get("validated_intent")]
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
  }
  labels = sorted(set(y_true) | set(y_pred))
  cm = pd.DataFrame(confusion_matrix(y_true, y_pred, labels=labels), index=labels, columns=labels)
  return (metrics, cm), rows


def clear_events():
  db = get_db()
  docs = list(db.collection("nlp_events").stream())
  for i in range(0, len(docs), 400):
    batch = db.batch()
    for d in docs[i:i+400]:
      batch.delete(d.reference)
    batch.commit()
  return len(docs)


def import_validations(df, actor_email: str):
  required = {"message", "predicted_intent", "validated_intent"}
  if not required.issubset(df.columns):
    raise ValueError("El CSV debe contener: message, predicted_intent, validated_intent")
  db = get_db()
  count = 0
  for _, row in df.iterrows():
    db.collection("nlp_events").add({
      "actor": actor_email,
      "message": str(row["message"]),
      "predicted_intent": str(row["predicted_intent"]),
      "validated_intent": str(row["validated_intent"]),
      "confidence": float(row.get("confidence", 0) or 0),
      "created_at": firestore.SERVER_TIMESTAMP,
      "validated_at": firestore.SERVER_TIMESTAMP,
      "validated_by": actor_email,
    })
    count += 1
  return count
