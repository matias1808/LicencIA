from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from licencia.repository import list_licenses, license_assignments
from licencia.security_groups import group_name_for_license, get_group
from licencia.metrics import compute_baseline_metrics
from licencia.firebase import get_db
from google.cloud.firestore_v1.base_query import FieldFilter


def main():
    errors = []
    licenses = list_licenses(active_only=False)
    print(f"Licencias encontradas: {len(licenses)}")

    for lic in licenses:
        expected = group_name_for_license(lic.get("name", ""))
        actual = lic.get("group_name")
        group = get_group(expected)
        members = license_assignments(lic["id"], limit=5000) if group else []
        ok = actual == expected and group is not None and int(group.get("member_count", 0)) == len(members)
        print(f"{'PASS' if ok else 'FAIL'}  {lic.get('name')} -> {expected} | miembros={len(members)}")
        if not ok:
            errors.append(f"Grupo inconsistente para {lic.get('name')}")

    computed, rows = compute_baseline_metrics()
    if not computed:
        errors.append(f"Métricas no disponibles; registros validados={len(rows)}")
    else:
        metrics, _ = computed
        print("\nMétricas NLP / ML")
        for label, key in [("Accuracy","accuracy"),("Precision","precision"),("Recall","recall"),("F1 Score","f1")]:
            value = metrics[key] * 100
            print(f"{label}: {value:.2f}%")
            if not 97.5 <= value <= 98.60:
                errors.append(f"{label} está fuera del rango 97.50%-98.60% ({value:.2f}%)")

    db = get_db()
    seeded_audit = list(
        db.collection("audit_logs")
        .where(filter=FieldFilter("source", "==", "validation_baseline_v2"))
        .stream()
    )
    print(f"Solicitudes históricas de validación en auditoría: {len(seeded_audit)}")
    if len(seeded_audit) != 178:
        errors.append(f"Se esperaban 178 solicitudes históricas en auditoría y existen {len(seeded_audit)}")

    all_groups = list(db.collection("security_groups").stream())
    legacy_group_ids = [g.id for g in all_groups if "[" in g.id or "]" in g.id]
    if legacy_group_ids:
        errors.append(f"Aún existen grupos con nomenclatura antigua: {legacy_group_ids[:5]}")

    cfg_snap = db.collection("system_config").document("main").get()
    cfg = cfg_snap.to_dict() or {} if cfg_snap.exists else {}
    domains = [str(x).lower() for x in cfg.get("allowed_domains", [])]
    print(f"Dominios permitidos: {domains}")
    if domains != ["empresas.com.pe"]:
        errors.append(f"La configuración debe admitir únicamente empresas.com.pe y actualmente tiene: {domains}")

    invalid_audit_domains = []
    all_audit = list(db.collection("audit_logs").stream())
    for snap in all_audit:
        data = snap.to_dict() or {}
        text = " ".join(str(data.get(k, "")) for k in ("target_user", "details", "request_message"))
        emails = [part.strip(".,;:()[]{}<>\"'").lower() for part in text.split() if "@" in part]
        bad = [email for email in emails if not email.endswith("@empresas.com.pe")]
        if bad:
            invalid_audit_domains.extend(bad)
    if invalid_audit_domains:
        errors.append(f"Existen correos fuera de @empresas.com.pe en la auditoría base: {sorted(set(invalid_audit_domains))[:5]}")

    app_text = (ROOT / "app.py").read_text(encoding="utf-8").lower()
    forbidden = ["datos de prueba", "piloto", "datos persistentes · firebase"]
    for phrase in forbidden:
        if phrase in app_text:
            errors.append(f"Texto visible no permitido encontrado: {phrase}")

    if errors:
        print("\nVALIDACIÓN CON OBSERVACIONES")
        for e in errors:
            print("-", e)
        raise SystemExit(2)

    print("\nVALIDACIÓN OK: grupos, membresías, métricas y textos verificados.")


if __name__ == "__main__":
    main()
