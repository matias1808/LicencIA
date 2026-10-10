\
"""
Compatibilidad con versiones anteriores.

Usa:
  python scripts/initialize_firestore.py

Este archivo NO borra datos. El reset destructivo está protegido y solo existe
en initialize_firestore.py con confirmación explícita.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from licencia.seed_data import seed_all

if __name__ == "__main__":
  if "--reset" in sys.argv or "--force-reset" in sys.argv:
    raise SystemExit(
      "Por seguridad este script ya no permite borrar datos. "
      "Usa scripts/initialize_firestore.py solo si sabes exactamente lo que haces."
    )
  print(seed_all(reset=False))
