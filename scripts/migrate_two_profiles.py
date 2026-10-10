from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from firebase_admin import firestore
from licencia.firebase import get_db
from licencia.auth import hash_password

ACCOUNTS=[
  {"email":"gestor.licencias@empresas.com.pe","display_name":"Gestor de Licencias","role":"license_manager","password":"LicencIA#Gestor2026!"},
  {"email":"admin.licencia@empresas.com.pe","display_name":"Administrador","role":"platform_admin","password":"LicencIA#Admin2026!"},
]
allowed={x["email"] for x in ACCOUNTS}
db=get_db()
for doc in list(db.collection("app_users").stream()):
  if doc.id.lower() not in allowed:
    doc.reference.delete()
for a in ACCOUNTS:
  db.collection("app_users").document(a["email"]).set({
    "email":a["email"],"display_name":a["display_name"],"role":a["role"],"active":True,
    "password_hash":hash_password(a["password"]),"must_change_password":False,"updated_at":firestore.SERVER_TIMESTAMP,
  },merge=True)
  db.collection("corporate_users").document(a["email"]).set({
    "email":a["email"],"display_name":a["display_name"],"department":"TI","active":True,
  },merge=True)
print("Perfiles de acceso actualizados: Gestor de licencias y Administrador.")
