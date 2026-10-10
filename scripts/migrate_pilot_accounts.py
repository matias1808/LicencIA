from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firebase_admin import firestore
from licencia.firebase import get_db
from licencia.auth import hash_password

NEW_ACCOUNTS = [
    {
        "email": "gestor.licencias@empresas.com.pe",
        "display_name": "Gestor de Licencias",
        "role": "license_manager",
        "password": "LicencIA#Gestor2026!",
    },
    {
        "email": "admin.licencia@empresas.com.pe",
        "display_name": "Administrador de LicencIA",
        "role": "platform_admin",
        "password": "LicencIA#Admin2026!",
    },
    {
        "email": "auditor.licencias@empresas.com.pe",
        "display_name": "Auditor de Licencias",
        "role": "auditor",
        "password": "LicencIA#Auditor2026!",
    },
    {
        "email": "consulta.licencias@empresas.com.pe",
        "display_name": "Usuario de Consulta",
        "role": "query_user",
        "password": "LicencIA#Consulta2026!",
    },
]

db = get_db()

# El entorno piloto inicial tenía únicamente cuentas de acceso de sistema.
# Capturamos sus IDs existentes y retiramos esas identidades sin depender
# de nombres anteriores escritos en el código.
existing_app_users = list(db.collection("app_users").stream())

for doc in existing_app_users:
    old_email = doc.id
    db.collection("app_users").document(old_email).delete()
    db.collection("corporate_users").document(old_email).delete()

for info in NEW_ACCOUNTS:
    email = info["email"]

    db.collection("app_users").document(email).set({
        "email": email,
        "display_name": info["display_name"],
        "role": info["role"],
        "active": True,
        "password_hash": hash_password(info["password"]),
        "must_change_password": True,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    db.collection("corporate_users").document(email).set({
        "email": email,
        "display_name": info["display_name"],
        "department": "TI",
        "active": True,
    }, merge=True)

print("Migración de cuentas completada.")
print("No se modificaron licencias, asignaciones ni auditoría.")
print("Cuentas iniciales del piloto:")
for info in NEW_ACCOUNTS:
    print("-", info["email"])
