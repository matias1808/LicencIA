from __future__ import annotations

import random
import re
import unicodedata

from firebase_admin import firestore

from .auth import hash_password
from .firebase import get_db
from .security_groups import group_name_for_license, member_doc_id
from .config import SECURITY_GROUPS_COLLECTION


DEFAULT_APP_ACCOUNTS = [
    {
        "email": "gestor.licencias@empresas.com.pe",
        "password": "LicencIA#Gestor2026!",
        "display_name": "Gestor de Licencias",
        "role": "license_manager",
        "can_write": True,
    },
    {
        "email": "admin.licencia@empresas.com.pe",
        "password": "LicencIA#Admin2026!",
        "display_name": "Administrador",
        "role": "platform_admin",
        "can_write": True,
    },
]

DEFAULT_LICENSES = [
    ("m365_e5", "M365 E5 Unified", "M365_E5_UNIFIED", "SPE_E5", 1900),
    ("m365_f3", "M365 F3 FUSL", "M365_F3_FUSL", "SPE_F1", 1900),
    ("m365_e3", "M365 E3", "M365_E3", "SPE_E3", 1900),
    ("eoa_exchange_online", "EOA Exchange Online", "EOA_EXCHANGE_ONLINE", "EXCHANGEARCHIVE_ADDON", 50),
    ("exchange_kiosk", "Exchange Kiosk", "EXCHANGE_KIOSK", "EXCHANGEDESKLESS", 50),
    ("exchange_p1", "Exchange P1", "EXCHANGE_P1", "EXCHANGESTANDARD", 50),
    ("exchange_p2", "Exchange P2", "EXCHANGE_P2", "EXCHANGEENTERPRISE", 50),
    ("planner_project_p3", "Planner & Project P3", "PLANNER_PROJECT_P3", "PROJECTPROFESSIONAL", 50),
    ("power_apps_premium", "Power Apps Premium", "POWER_APPS_PREMIUM", "POWERAPPS_PER_USER", 50),
    ("power_automate_premium", "Power Automate Premium", "POWER_AUTOMATE_PREMIUM", "POWERAUTOMATE_ATTENDED_RPA", 50),
    ("power_bi_premium_usl", "Power BI Premium USL", "POWER_BI_PREMIUM_USL", "PBI_PREMIUM_PER_USER", 50),
    ("visio_p2", "Visio P2", "VISIO_P2", "VISIOCLIENT", 50),
    ("w365_ent_4_16_128", "W365 Ent 4vCPU/16GB/128GB", "W365_ENT_4VCPU_16GB_128GB", "CPC_E_4C_16GB_128GB", 50),
]


def _slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", ".", s).strip(".")


def generate_users(n: int = 1900):
    first_names = [
        "Juan", "Maria", "Carlos", "Ana", "Luis", "Lucia", "Diego", "Andrea", "Jorge", "Valeria",
        "Miguel", "Camila", "Pedro", "Daniela", "Jose", "Paola", "Renato", "Fiorella", "Alonso", "Carla",
        "Sergio", "Natalia", "Rafael", "Claudia", "Fernando", "Gabriela", "Marco", "Alejandra", "Victor", "Melissa",
        "Ricardo", "Patricia", "Eduardo", "Sofia", "Martin", "Vanessa", "Raul", "Diana", "Oscar", "Micaela",
        "Bruno", "Nicole", "Hector", "Adriana", "Julio", "Ximena", "Gonzalo", "Romina", "Ivan", "Elena",
    ]
    last_names = [
        "Perez", "Garcia", "Rodriguez", "Sanchez", "Lopez", "Torres", "Flores", "Ramirez", "Vargas", "Rojas",
        "Castillo", "Diaz", "Mendoza", "Chavez", "Fernandez", "Gonzales", "Silva", "Herrera", "Medina", "Aguilar",
        "Navarro", "Paredes", "Campos", "Salazar", "Reyes", "Cruz", "Vega", "Espinoza", "Valdez", "Cabrera",
        "Morales", "Fuentes", "Arias", "Ortega", "Delgado", "Palomino", "Acosta", "Molina", "Cardenas", "Benavides",
    ]
    depts = ["TI", "Operaciones", "Finanzas", "Comercial", "RRHH", "Riesgos", "Legal", "Marketing"]
    out = []
    i = 0
    for first in first_names:
        for last in last_names:
            i += 1
            if i > n:
                return out
            domain = "empresas.com.pe"
            email = f"{_slug(first)}.{_slug(last)}{i:04d}@{domain}"
            out.append({
                "email": email,
                "display_name": f"{first} {last}",
                "department": depts[(i - 1) % len(depts)],
                "active": True,
            })
    return out


def _delete_collection(collection_ref):
    docs = list(collection_ref.stream())
    for i in range(0, len(docs), 350):
        batch = get_db().batch()
        for d in docs[i:i + 350]:
            batch.delete(d.reference)
        batch.commit()


def seed_all(reset: bool = False, seed: int = 42, allow_destructive: bool = False):
    db = get_db()
    rng = random.Random(seed)

    marker = db.collection("system_config").document("main").get()
    if marker.exists:
        existing = marker.to_dict() or {}
        if existing.get("initialized", False) and not reset:
            return {"status": "already_initialized", "message": "La base ya está inicializada. No se modificó ningún dato existente."}

    if reset and not allow_destructive:
        raise RuntimeError("Reset destructivo bloqueado. Debes confirmarlo explícitamente.")

    if reset:
        for g in db.collection(SECURITY_GROUPS_COLLECTION).stream():
            _delete_collection(g.reference.collection("members"))
            g.reference.delete()
        for name in ["assignments", "licenses", "corporate_users", "app_users", "audit_logs", "nlp_events"]:
            _delete_collection(db.collection(name))

    users = generate_users(1900)
    for i in range(0, len(users), 350):
        batch = db.batch()
        for u in users[i:i + 350]:
            batch.set(db.collection("corporate_users").document(u["email"]), u)
        batch.commit()

    for a in DEFAULT_APP_ACCOUNTS:
        db.collection("app_users").document(a["email"]).set({
            "email": a["email"], "display_name": a["display_name"], "role": a["role"],
            "active": True, "can_write": a["can_write"], "qa_only": False,
            "password_hash": hash_password(a["password"]), "must_change_password": False,
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    db.collection("system_config").document("main").set({
        "allowed_domains": ["empresas.com.pe"],
        "simulate_integration_failure": False,
        "integration_mode": "firestore",
        "integration_name": "Security Groups",
        "initialized": True,
        "seed_version": 3,
        "initialized_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    for license_id, name, sku, graph_sku, total in DEFAULT_LICENSES:
        ratio = rng.uniform(0.75, 0.95)
        assigned = min(int(round(total * ratio)), len(users))
        group_name = group_name_for_license(name)
        db.collection("licenses").document(license_id).set({
            "name": name, "sku": sku, "graph_sku": graph_sku, "group_name": group_name,
            "total_stock": total, "assigned_count": assigned, "active": True, "suite": total == 1900,
        })
        gref = db.collection(SECURITY_GROUPS_COLLECTION).document(group_name)
        gref.set({
            "name": group_name, "license_id": license_id, "license_name": name,
            "active": True, "member_count": assigned,
            "created_at": firestore.SERVER_TIMESTAMP, "updated_at": firestore.SERVER_TIMESTAMP,
        })
        chosen = rng.sample(users, assigned)
        for i in range(0, len(chosen), 350):
            batch = db.batch()
            for u in chosen[i:i + 350]:
                batch.set(gref.collection("members").document(member_doc_id(u["email"])), {
                    "user_email": u["email"], "license_id": license_id, "license_name": name,
                    "group_name": group_name, "added_by": "sistema.licencia@empresas.com.pe",
                    "created_at": firestore.SERVER_TIMESTAMP,
                })
            batch.commit()

    return {"status": "initialized", "users": len(users), "licenses": len(DEFAULT_LICENSES), "accounts": len(DEFAULT_APP_ACCOUNTS)}
