\
from __future__ import annotations

import random
import re
import unicodedata
from pathlib import Path

from firebase_admin import firestore

from .auth import hash_password
from .firebase import get_db

DEFAULT_APP_ACCOUNTS = [
  {
    "email": "gestor.licencias@empresas.com.pe",
    "password": "LicencIA#Gestor2026!",
    "display_name": "Gestor de Licencias",
    "role": "license_manager",
  },
  {
    "email": "admin.licencia@empresas.com.pe",
    "password": "LicencIA#Admin2026!",
    "display_name": "Administrador",
    "role": "platform_admin",
  },
]

DEFAULT_LICENSES = [
  ("m365_e5", "M365 E5 Unified", "M365_E5_UNIFIED", 1900),
  ("m365_f3", "M365 F3 FUSL", "M365_F3_FUSL", 1900),
  ("m365_e3", "M365 E3", "M365_E3", 1900),
  ("eoa_exchange_online", "EOA Exchange Online", "EOA_EXCHANGE_ONLINE", 50),
  ("exchange_kiosk", "Exchange Kiosk", "EXCHANGE_KIOSK", 50),
  ("exchange_p1", "Exchange P1", "EXCHANGE_P1", 50),
  ("exchange_p2", "Exchange P2", "EXCHANGE_P2", 50),
  ("planner_project_p3", "Planner & Project P3", "PLANNER_PROJECT_P3", 50),
  ("power_apps_premium", "Power Apps Premium", "POWER_APPS_PREMIUM", 50),
  ("power_automate_premium", "Power Automate Premium", "POWER_AUTOMATE_PREMIUM", 50),
  ("power_bi_premium_usl", "Power BI Premium USL", "POWER_BI_PREMIUM_USL", 50),
  ("visio_p2", "Visio P2", "VISIO_P2", 50),
  ("w365_ent_4_16_128", "W365 Ent 4vCPU/16GB/128GB", "W365_ENT_4VCPU_16GB_128GB", 50),
]


def _slug(text: str) -> str:
  s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
  s = re.sub(r"[^a-z0-9]+", ".", s).strip(".")
  return s


def generate_users(n=1900):
  first_names = [
    "Juan","Maria","Carlos","Ana","Luis","Lucia","Diego","Andrea","Jorge","Valeria",
    "Miguel","Camila","Pedro","Daniela","Jose","Paola","Renato","Fiorella","Alonso","Carla",
    "Sergio","Natalia","Rafael","Claudia","Fernando","Gabriela","Marco","Alejandra","Victor","Melissa",
    "Ricardo","Patricia","Eduardo","Sofia","Martin","Vanessa","Raul","Diana","Oscar","Micaela",
    "Bruno","Nicole","Hector","Adriana","Julio","Ximena","Gonzalo","Romina","Ivan","Elena",
  ]
  last_names = [
    "Perez","Garcia","Rodriguez","Sanchez","Lopez","Torres","Flores","Ramirez","Vargas","Rojas",
    "Castillo","Diaz","Mendoza","Chavez","Fernandez","Gonzales","Silva","Herrera","Medina","Aguilar",
    "Navarro","Paredes","Campos","Salazar","Reyes","Cruz","Vega","Espinoza","Valdez","Cabrera",
    "Morales","Fuentes","Arias","Ortega","Delgado","Palomino","Acosta","Molina","Cardenas","Benavides",
  ]
  depts = ["TI", "Operaciones", "Finanzas", "Comercial", "RRHH", "Riesgos", "Legal", "Marketing"]
  out = []
  i = 0
  for first in first_names:
    for last in last_names:
      i += 1
      if i > n:
        return out
      # El índice evita colisiones aunque haya nombres repetidos en una carga futura.
      email = f"{_slug(first)}.{_slug(last)}{i:04d}@empresas.com.pe"
      out.append({
        "email": email,
        "display_name": f"{first} {last}",
        "department": depts[(i - 1) % len(depts)],
        "active": True,
      })
  return out


def seed_all(reset=False, seed=42, allow_destructive=False):
  db = get_db()
  rng = random.Random(seed)

  marker = db.collection("system_config").document("main").get()
  if marker.exists:
    existing = marker.to_dict() or {}
    if existing.get("initialized", False) and not reset:
      return {
        "status": "already_initialized",
        "message": "La base ya está inicializada. No se modificó ningún dato existente.",
      }

  if reset and not allow_destructive:
    raise RuntimeError(
      "Reset destructivo bloqueado. Para borrar datos debes usar el script protegido "
      "y confirmar explícitamente la operación."
    )

  if reset:
    for collection in ["assignments", "licenses", "corporate_users", "app_users", "audit_logs", "nlp_events"]:
      docs = list(db.collection(collection).stream())
      for i in range(0, len(docs), 400):
        batch = db.batch()
        for d in docs[i:i+400]:
          batch.delete(d.reference)
        batch.commit()

  users = generate_users(1900)

  # Asegura que las cuentas de acceso también existan como identidades corporativas.
  for offset, a in enumerate(DEFAULT_APP_ACCOUNTS, start=1):
    users[-offset] = {
      "email": a["email"],
      "display_name": a["display_name"],
      "department": "TI",
      "active": True,
    }

  # Usuarios corporativos
  for i in range(0, len(users), 400):
    batch = db.batch()
    for u in users[i:i+400]:
      batch.set(db.collection("corporate_users").document(u["email"]), u)
    batch.commit()

  # Cuentas de acceso
  for a in DEFAULT_APP_ACCOUNTS:
    db.collection("app_users").document(a["email"]).set({
      "email": a["email"],
      "display_name": a["display_name"],
      "role": a["role"],
      "active": True,
      "password_hash": hash_password(a["password"]),
      "must_change_password": False,
      "created_at": firestore.SERVER_TIMESTAMP,
    })

  # Configuración
  db.collection("system_config").document("main").set({
    "allowed_domains": ["empresas.com.pe"],
    "simulate_integration_failure": False,
    "integration_name": "Firebase Connector",
    "initialized": True,
    "seed_version": 1,
    "initialized_at": firestore.SERVER_TIMESTAMP,
  }, merge=True)

  # Licencias + asignaciones (75%–95% consumido)
  for license_id, name, sku, total in DEFAULT_LICENSES:
    ratio = rng.uniform(0.75, 0.95)
    assigned = min(int(round(total * ratio)), len(users))
    group_name = f"GRP_LICENCIASMS[{sku}]_USERS"
    db.collection("licenses").document(license_id).set({
      "name": name,
      "sku": sku,
      "group_name": group_name,
      "total_stock": total,
      "assigned_count": assigned,
      "active": True,
      "suite": total == 1900,
    })

    chosen = rng.sample(users, assigned)
    rows = []
    for u in chosen:
      safe = u["email"].replace("@", "__at__").replace(".", "_")
      ref = db.collection("assignments").document(f"{license_id}__{safe}")
      rows.append((ref, {
        "user_email": u["email"],
        "license_id": license_id,
        "license_name": name,
        "group_name": group_name,
        "assigned_by": "system@licencia.local",
        "created_at": firestore.SERVER_TIMESTAMP,
      }))
    for i in range(0, len(rows), 400):
      batch = db.batch()
      for ref, payload in rows[i:i+400]:
        batch.set(ref, payload)
      batch.commit()

  return {
    "users": len(users),
    "licenses": len(DEFAULT_LICENSES),
    "accounts": len(DEFAULT_APP_ACCOUNTS),
  }
