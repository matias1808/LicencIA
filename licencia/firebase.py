\
from __future__ import annotations
from pathlib import Path
import tomllib

import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st


def _from_streamlit_secrets():
  try:
    if "firebase" in st.secrets:
      return dict(st.secrets["firebase"])
  except Exception:
    pass
  return None


def _from_local_toml():
  root = Path(__file__).resolve().parents[1]
  path = root / ".streamlit" / "secrets.toml"
  if not path.exists():
    return None
  with path.open("rb") as f:
    data = tomllib.load(f)
  return dict(data.get("firebase", {})) or None


def _firebase_credential_dict() -> dict:
  data = _from_streamlit_secrets() or _from_local_toml()
  if not data:
    raise RuntimeError(
      "No se encontraron credenciales Firebase. Configura [firebase] en "
      ".streamlit/secrets.toml o en los Secrets de Streamlit Community Cloud."
    )
  if "private_key" in data:
    data["private_key"] = str(data["private_key"]).replace("\\\\n", "\\n")
  return data


@st.cache_resource(show_spinner=False)
def get_db():
  try:
    firebase_admin.get_app()
  except ValueError:
    cred = credentials.Certificate(_firebase_credential_dict())
    firebase_admin.initialize_app(cred)
  return firestore.client()
