from pathlib import Path
from _transformer_common import prepare
ROOT=Path(__file__).resolve().parents[1]
prepare("dccuchile/bert-base-spanish-wwm-cased", ROOT/"models"/"beto_intent_v3")
