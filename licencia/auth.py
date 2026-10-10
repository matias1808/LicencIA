from __future__ import annotations
import bcrypt
from firebase_admin import firestore

from .firebase import get_db


def hash_password(password: str) -> str:
  return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
  try:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
  except Exception:
    return False


def authenticate(email: str, password: str):
  email = (email or "").strip().lower()
  if not email or not password:
    return None
  db = get_db()
  snap = db.collection("app_users").document(email).get()
  if not snap.exists:
    return None
  data = snap.to_dict()
  if not data.get("active", True):
    return None
  if not verify_password(password, data.get("password_hash", "")):
    return None
  db.collection("audit_logs").add({
    "action": "LOGIN",
    "actor": email,
    "target_user": email,
    "license_id": None,
    "result": "SUCCESS",
    "details": "Inicio de sesión correcto",
    "created_at": firestore.SERVER_TIMESTAMP,
  })
  data["email"] = email
  return data


def change_password(email: str, new_password: str):
  db = get_db()
  db.collection("app_users").document(email.lower()).update({
    "password_hash": hash_password(new_password),
    "must_change_password": False,
    "updated_at": firestore.SERVER_TIMESTAMP,
  })
