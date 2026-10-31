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


def _audit_login(email: str, result: str, details: str) -> None:
    """Registra accesos exitosos y rechazados sin almacenar contraseñas ni secretos."""
    try:
        get_db().collection("audit_logs").add({
            "action": "LOGIN",
            "actor": (email or "").strip().lower() or "unknown",
            "target_user": (email or "").strip().lower() or None,
            "license_id": None,
            "group_name": None,
            "result": result,
            "details": details,
            "operation_id": None,
            "integration": "AUTH",
            "created_at": firestore.SERVER_TIMESTAMP,
        })
    except Exception:
        # Un fallo de auditoría no debe filtrar información ni reemplazar el resultado de autenticación.
        pass


def authenticate(email: str, password: str):
    email = (email or "").strip().lower()
    if not email or not password:
        if email:
            _audit_login(email, "DENIED", "Intento de acceso rechazado: credenciales inválidas o incompletas.")
        return None

    db = get_db()
    snap = db.collection("app_users").document(email).get()
    if not snap.exists:
        _audit_login(email, "DENIED", "Intento de acceso rechazado: credenciales inválidas o cuenta no habilitada.")
        return None

    data = snap.to_dict() or {}
    if not data.get("active", True):
        _audit_login(email, "DENIED", "Intento de acceso rechazado: credenciales inválidas o cuenta no habilitada.")
        return None

    if not verify_password(password, data.get("password_hash", "")):
        _audit_login(email, "DENIED", "Intento de acceso rechazado: credenciales inválidas o cuenta no habilitada.")
        return None

    _audit_login(email, "SUCCESS", "Inicio de sesión correcto.")
    data["email"] = email
    data.setdefault("can_write", True)
    data.setdefault("admin_access", data.get("role") == "platform_admin")
    return data


def change_password(email: str, new_password: str):
    db = get_db()
    db.collection("app_users").document(email.lower()).update({
        "password_hash": hash_password(new_password),
        "must_change_password": False,
        "updated_at": firestore.SERVER_TIMESTAMP,
    })
