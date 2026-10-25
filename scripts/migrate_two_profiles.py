from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firebase_admin import firestore
from licencia.firebase import get_db
from licencia.auth import hash_password

ACCOUNTS = [
    {
        "email": "gestor.licencias@empresas.com.pe",
        "display_name": "Gestor de Licencias",
        "role": "license_manager",
        "password": "LicencIA#Gestor2026!",
        "can_write": True,
    },
    {
        "email": "admin.licencia@empresas.com.pe",
        "display_name": "Administrador",
        "role": "platform_admin",
        "password": "LicencIA#Admin2026!",
        "can_write": True,
    },
]


def main():
    db = get_db()
    allowed = {x["email"] for x in ACCOUNTS}

    # Conserva las cuentas qa_only creadas por migrate_28cp.py; no son un perfil funcional.
    for doc in list(db.collection("app_users").stream()):
        data = doc.to_dict() or {}
        if doc.id.lower() not in allowed and not data.get("qa_only", False):
            doc.reference.delete()

    for a in ACCOUNTS:
        db.collection("app_users").document(a["email"]).set({
            "email": a["email"],
            "display_name": a["display_name"],
            "role": a["role"],
            "active": True,
            "can_write": a["can_write"],
            "qa_only": False,
            "password_hash": hash_password(a["password"]),
            "must_change_password": False,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    print("Perfiles funcionales actualizados: Gestor de licencias y Administrador.")


if __name__ == "__main__":
    main()
