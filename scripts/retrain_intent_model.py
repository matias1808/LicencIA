from pathlib import Path
import json, hashlib
import pandas as pd
import joblib

from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "nlp_training_v2.csv"
CHALLENGE = ROOT / "data" / "nlp_challenge_v2.csv"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

train_df = pd.read_csv(TRAIN)
challenge_df = pd.read_csv(CHALLENGE)

features = FeatureUnion([
  ("word", TfidfVectorizer(
    lowercase=True, strip_accents="unicode",
    ngram_range=(1, 3), min_df=2, max_df=0.995,
    sublinear_tf=True, max_features=65000
  )),
  ("char", TfidfVectorizer(
    lowercase=True, strip_accents="unicode",
    analyzer="char_wb", ngram_range=(3, 5),
    min_df=2, sublinear_tf=True, max_features=75000
  )),
])

model = Pipeline([
  ("features", features),
  ("clf", SGDClassifier(
    loss="log_loss", penalty="l2", alpha=1e-5,
    max_iter=2500, tol=1e-4, class_weight="balanced",
    random_state=42, average=True
  )),
])

print(f"Entrenando con {len(train_df):,} ejemplos...")
model.fit(train_df["text"], train_df["intent"])

pred = model.predict(challenge_df["text"])
acc = accuracy_score(challenge_df["intent"], pred)
precision, recall, f1, _ = precision_recall_fscore_support(
  challenge_df["intent"], pred, average="weighted", zero_division=0
)

model_path = MODEL_DIR / "intent_model_v2.joblib"
joblib.dump(model, model_path, compress=3)

metadata = {
  "model_name": "LicencIA Intent Classifier v2",
  "model_type": "TF-IDF palabras (1-3) + caracteres (3-5) + SGD log-loss",
  "training_examples": len(train_df),
  "challenge_examples": len(challenge_df),
  "challenge_accuracy": acc,
  "challenge_precision_weighted": precision,
  "challenge_recall_weighted": recall,
  "challenge_f1_weighted": f1,
  "evaluation_note": "Challenge sintético separado; no sustituye la validación real.",
  "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
}
(MODEL_DIR / "intent_model_v2_metadata.json").write_text(
  json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
)

print(classification_report(challenge_df["intent"], pred, zero_division=0))
print(json.dumps(metadata, indent=2))
