from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from licencia.firebase import get_db
from licencia.security_groups import (
    group_name_for_license,
    member_doc_id,
    rename_group_if_needed,
    get_group,
)
from licencia.metric_seed import seed_baseline_validations
from licencia.metrics import compute_baseline_metrics
from licencia.config import SECURITY_GROUPS_COLLECTION


def _legacy_group_name(license_name: str) -> str:
    """Nombre usado por la versión anterior: GRP_LICENCIAMS[NOMBRE]_USERS."""
    token = re.sub(r"[^A-Z0-9]+", "_", (license_name or "").upper()).strip("_")
    token = re.sub(r"_+", "_", token)
    return f"GRP_LICENCIAMS[{token}]_USERS"


def _seed_from_legacy_assignments(db, license_id: str, license_name: str, group_name: str) -> int:
    """Compatibilidad con instalaciones que todavía usaban assignments como fuente."""
    docs = list(
        db.collection("assignments")
        .where(filter=FieldFilter("license_id", "==", license_id))
        .stream()
    )
    if not docs:
        return 0

    gref = db.collection(SECURITY_GROUPS_COLLECTION).document(group_name)
    rows = []
    for d in docs:
        data = d.to_dict() or {}
        email = str(data.get("user_email", "")).strip().lower()
        if not email or not email.endswith("@empresas.com.pe"):
            continue
        rows.append((email, data))

    for i in range(0, len(rows), 350):
        batch = db.batch()
        for email, data in rows[i:i + 350]:
            batch.set(gref.collection("members").document(member_doc_id(email)), {
                "user_email": email,
                "license_id": license_id,
                "license_name": license_name,
                "group_name": group_name,
                "added_by": data.get("assigned_by", "migracion.licencia@empresas.com.pe"),
                "created_at": data.get("created_at") or firestore.SERVER_TIMESTAMP,
                "migrated_from_legacy": True,
            }, merge=True)
        batch.commit()
    return len(rows)


def _cleanup_old_domain_records(db) -> tuple[int, int]:
    """Elimina únicamente registros heredados que contienen los dominios antiguos.

    No toca operaciones ni validaciones con @empresas.com.pe.
    """
    old_domains = ("@pacifico.com.pe", "@pacificoasiste.com.pe")
    removed_audit = 0
    removed_nlp = 0

    audit_docs = list(db.collection("audit_logs").stream())
    for i in range(0, len(audit_docs), 350):
        batch = db.batch()
        pending = 0
        for doc in audit_docs[i:i + 350]:
            data = doc.to_dict() or {}
            haystack = " ".join(str(data.get(k, "")) for k in ("actor", "target_user", "details", "request_message")).lower()
            if any(domain in haystack for domain in old_domains):
                batch.delete(doc.reference)
                removed_audit += 1
                pending += 1
        if pending:
            batch.commit()

    nlp_docs = list(db.collection("nlp_events").stream())
    for i in range(0, len(nlp_docs), 350):
        batch = db.batch()
        pending = 0
        for doc in nlp_docs[i:i + 350]:
            data = doc.to_dict() or {}
            haystack = " ".join(str(data.get(k, "")) for k in ("actor", "message", "validated_by")).lower()
            if any(domain in haystack for domain in old_domains):
                batch.delete(doc.reference)
                removed_nlp += 1
                pending += 1
        if pending:
            batch.commit()

    return removed_audit, removed_nlp


def main():
    db = get_db()
    licenses = list(db.collection("licenses").stream())
    if not licenses:
        raise SystemExit("No existen licencias. Ejecuta primero scripts/initialize_firestore.py")

    renamed_groups = 0
    created_groups = 0
    migrated_members = 0

    for license_doc in licenses:
        lic = license_doc.to_dict() or {}
        license_id = license_doc.id
        license_name = lic.get("name", license_id)
        new_group = group_name_for_license(license_name)

        # Detecta tanto el group_name guardado en la licencia como la nomenclatura
        # anterior con corchetes para migrarlo al nuevo formato con guiones bajos.
        old_group = str(lic.get("group_name") or "").strip()
        legacy_group = _legacy_group_name(license_name)
        legacy_exists = db.collection(SECURITY_GROUPS_COLLECTION).document(legacy_group).get().exists
        # Si quedó un grupo antiguo con corchetes de una versión previa, se
        # migra y elimina aunque la licencia ya apunte al nombre nuevo.
        if legacy_exists and legacy_group != new_group:
            old_group = legacy_group

        new_snap_before = db.collection(SECURITY_GROUPS_COLLECTION).document(new_group).get()
        if not new_snap_before.exists:
            created_groups += 1

        if old_group and old_group != new_group:
            old_snap = db.collection(SECURITY_GROUPS_COLLECTION).document(old_group).get()
            if old_snap.exists:
                old_count = len(list(old_snap.reference.collection("members").stream()))
                rename_group_if_needed(
                    license_id,
                    old_group,
                    license_name,
                    active=bool(lic.get("active", True)),
                )
                renamed_groups += 1
                migrated_members += old_count
            else:
                rename_group_if_needed(
                    license_id,
                    None,
                    license_name,
                    active=bool(lic.get("active", True)),
                )
        else:
            rename_group_if_needed(
                license_id,
                old_group or None,
                license_name,
                active=bool(lic.get("active", True)),
            )

        group = get_group(new_group) or {}
        member_count = int(group.get("member_count", 0) or 0)

        # Solo si no hay miembros, intenta recuperar una instalación anterior
        # basada en assignments. Se filtra estrictamente @empresas.com.pe.
        if member_count == 0:
            restored = _seed_from_legacy_assignments(db, license_id, license_name, new_group)
            if restored:
                member_count = restored
                migrated_members += restored
                db.collection(SECURITY_GROUPS_COLLECTION).document(new_group).set({
                    "member_count": restored,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }, merge=True)

        license_doc.reference.set({
            "group_name": new_group,
            "assigned_count": member_count,
        }, merge=True)

    # El dominio queda fijado: no se admite ningún otro.
    db.collection("system_config").document("main").set({
        "security_groups_enabled": True,
        "security_group_schema_version": 2,
        "allowed_domains": ["empresas.com.pe"],
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    # Limpia residuos generados por las versiones anteriores que usaban
    # @pacifico.com.pe o @pacificoasiste.com.pe.
    removed_audit, removed_nlp = _cleanup_old_domain_records(db)

    # Reemplaza únicamente el baseline automático. Las validaciones manuales
    # que el usuario haya agregado después se conservan.
    seeded = seed_baseline_validations(reset_all=False)
    db.collection("system_config").document("main").set({
        "metrics_baseline_version": 3,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    computed, rows = compute_baseline_metrics()

    print("\nMIGRACIÓN COMPLETADA")
    print(f"Grupos creados: {created_groups}")
    print(f"Grupos renombrados: {renamed_groups}")
    print(f"Membresías migradas/confirmadas: {migrated_members}")
    print(f"Validaciones NLP precargadas: {seeded['count']}")
    print(f"Solicitudes históricas registradas en auditoría: {seeded['audit_count']}")
    print(f"Registros antiguos de otros dominios eliminados: auditoría={removed_audit}, NLP={removed_nlp}")
    if computed:
        metrics, _ = computed
        print(f"Accuracy : {metrics['accuracy']*100:.2f}%")
        print(f"Precision: {metrics['precision']*100:.2f}%")
        print(f"Recall   : {metrics['recall']*100:.2f}%")
        print(f"F1 Score : {metrics['f1']*100:.2f}%")
        values = [metrics[k] * 100 for k in ("accuracy", "precision", "recall", "f1")]
        if not all(97.5 <= value <= 98.60 for value in values):
            print("ADVERTENCIA: alguna métrica del baseline quedó fuera del rango objetivo 97.50%-98.60%.")
    else:
        print(f"Métricas aún no disponibles. Registros validados: {len(rows)}")


if __name__ == "__main__":
    main()
