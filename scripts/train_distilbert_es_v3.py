from pathlib import Path
from _transformer_common import prepare
ROOT=Path(__file__).resolve().parents[1]
# DistilBERT con vocabulario reducido al español, adecuado como student/base ligero.
prepare("Recognai/distilbert-base-es-multilingual-cased", ROOT/"models"/"distilbert_es_intent_v3")
