from __future__ import annotations

import re
from typing import Iterable

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .firebase import get_db
from .config import (
    AUTHORIZED_GROUP_PATTERN,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_INTEGRATION_MODE,
    SUPPORTED_INTEGRATION_MODES,
    WRITE_ROLES,
)
from .integration import (
    GraphIntegrationError,
    get_graph_client,
    graph_configured,
)
from .security_groups import (
    group_name_for_license, ensure_group, get_group, group_member_count,
    memberships_for_user, list_members as list_group_members,
    assign_member, unassign_member, reassign_member, bulk_reassign_members,
    rename_group_if_needed,
)


class LicencIAError(Exception):
    pass


class PermissionDenied(LicencIAError):
    pass


class ValidationError(LicencIAError):
    pass


class IntegrationError(LicencIAError):
    pass


def get_system_config() -> dict:
    db = get_db()
    snap = db.collection("system_config").document("main").get()
    base = {
        "allowed_domains": DEFAULT_ALLOWED_DOMAINS,
        "simulate_integration_failure": False,
        "simulate_reassignment_failure": False,
        "integration_mode": DEFAULT_INTEGRATION_MODE,
        "integration_name": "Firebase / Firestore",
    }
    if snap.exists:
        base.update(snap.to_dict() or {})
    mode = str(base.get("integration_mode", DEFAULT_INTEGRATION_MODE)).lower()
    if mode not in SUPPORTED_INTEGRATION_MODES:
        mode = DEFAULT_INTEGRATION_MODE
    base["integration_mode"] = mode
    return base


def update_system_config(values: dict):
    values = dict(values)
    if "integration_mode" in values:
        mode = str(values["integration_mode"]).lower()
        if mode not in SUPPORTED_INTEGRATION_MODES:
            raise ValidationError(f"Modo de integración no soportado: {mode}")
        values["integration_mode"] = mode
        if "integration_name" not in values:
            values["integration_name"] = (
                "Microsoft Graph / Entra ID / Microsoft 365" if mode == "graph" else "Firebase / Firestore"
            )
    get_db().collection("system_config").document("main").set(values, merge=True)


def _mode() -> str:
    return get_system_config().get("integration_mode", DEFAULT_INTEGRATION_MODE)


def actor_can_write(actor: dict | None) -> bool:
    actor = actor or {}
    return actor.get("role") in WRITE_ROLES and actor.get("can_write", True) is not False


def _integration_label() -> str:
    return "Microsoft Graph" if _mode() == "graph" else "Firebase / Firestore"


def _audit(action, actor, target_user, license_id, result, details="", operation_id=None, group_name=None):
    get_db().collection("audit_logs").add({
        "action": action,
        "actor": actor,
        "target_user": target_user,
        "license_id": license_id,
        "group_name": group_name,
        "result": result,
        "details": details,
        "operation_id": operation_id,
        "integration": _integration_label(),
        "created_at": firestore.SERVER_TIMESTAMP,
    })


def _assert_write(actor: dict, action: str, target_user: str | None, license_id: str | None):
    if not actor_can_write(actor):
        _audit(
            action,
            (actor or {}).get("email"),
            target_user,
            license_id,
            "DENIED",
            "Intento de modificación bloqueado por permisos insuficientes.",
        )
        raise PermissionDenied("No tienes permisos para modificar licencias. La operación fue bloqueada.")


def corporate_email_allowed(email: str) -> bool:
    """LicencIA acepta exclusivamente identidades @empresas.com.pe."""
    email = (email or "").strip().lower()
    return email.endswith("@empresas.com.pe")


def get_corporate_user(email: str):
    db = get_db()
    snap = db.collection("corporate_users").document((email or "").strip().lower()).get()
    return snap.to_dict() if snap.exists else None


def validate_corporate_user(email: str) -> dict:
    email = (email or "").strip().lower()
    if not corporate_email_allowed(email):
        raise ValidationError("El correo no pertenece a un dominio corporativo permitido.")
    user = get_corporate_user(email)
    if not user:
        raise ValidationError("El usuario corporativo no existe en el listado oficial cargado.")
    if not user.get("active", True):
        raise ValidationError("El usuario corporativo existe, pero se encuentra deshabilitado.")
    return user


def list_corporate_users(limit: int = 2000):
    db = get_db()
    return [d.to_dict() for d in db.collection("corporate_users").limit(limit).stream()]


def _read_license_docs(active_only: bool = False) -> list[dict]:
    docs = get_db().collection("licenses").stream()
    items = []
    for d in docs:
        x = d.to_dict() or {}
        x["id"] = d.id
        if active_only and not x.get("active", True):
            continue
        # La membresía del grupo de seguridad es la fuente de verdad del beneficio.
        x["group_name"] = group_name_for_license(x.get("name", ""))
        group = get_group(x["group_name"])
        if group:
            x["assigned_count"] = int(group.get("member_count", 0) or 0)
            x["security_group_exists"] = True
        else:
            x["security_group_exists"] = False
        items.append(x)
    return sorted(items, key=lambda x: x.get("name", ""))

def _validate_group_shape(group_name: str) -> None:
    if not re.fullmatch(AUTHORIZED_GROUP_PATTERN, group_name or ""):
        raise ValidationError("La nomenclatura del grupo de seguridad no está autorizada.")


def validate_group_name(group_name: str) -> dict:
    """Valida la nomenclatura y que exista un único grupo de seguridad asociado a una licencia."""
    group_name = (group_name or "").strip()
    _validate_group_shape(group_name)
    group = get_group(group_name)
    if not group:
        raise ValidationError("El grupo de seguridad no existe en el catálogo autorizado de LicencIA.")
    if not group.get("active", True):
        raise ValidationError("El grupo de seguridad se encuentra deshabilitado.")
    license_id = group.get("license_id")
    if not license_id:
        raise ValidationError("El grupo de seguridad no tiene una licencia asociada.")
    snap = get_db().collection("licenses").document(license_id).get()
    if not snap.exists:
        raise ValidationError("La licencia asociada al grupo no existe.")
    data = snap.to_dict() or {}
    data["id"] = snap.id
    data["group_name"] = group_name
    data["assigned_count"] = int(group.get("member_count", 0) or 0)
    if not data.get("active", True):
        raise ValidationError("El grupo corresponde a una licencia deshabilitada.")
    return data

def _graph_client_or_error():
    if not graph_configured():
        raise IntegrationError(
            "El modo Microsoft Graph está activo, pero faltan credenciales [azure] en Secrets."
        )
    try:
        return get_graph_client()
    except GraphIntegrationError as e:
        raise IntegrationError(str(e)) from e


def _enrich_with_graph_inventory(items: list[dict]) -> list[dict]:
    if _mode() != "graph":
        for x in items:
            x.setdefault("inventory_source", "Firebase / Firestore")
        return items
    client = _graph_client_or_error()
    try:
        inv = client.sku_inventory()
    except GraphIntegrationError as e:
        raise IntegrationError(str(e)) from e
    for x in items:
        key = str(x.get("graph_sku") or x.get("sku") or "").upper()
        if key and key in inv:
            x["total_stock"] = inv[key]["total_stock"]
            x["assigned_count"] = inv[key]["assigned_count"]
            x["inventory_source"] = "Microsoft Graph / subscribedSkus"
            x["graph_sku_mapped"] = True
        else:
            # No se inventa stock de Microsoft 365: queda explícito que falta mapeo.
            x["inventory_source"] = "Firebase / Firestore (sin graph_sku mapeado)"
            x["graph_sku_mapped"] = False
    return items


def list_licenses(active_only: bool = False):
    return _enrich_with_graph_inventory(_read_license_docs(active_only=active_only))


def get_license(license_id: str):
    snap = get_db().collection("licenses").document(license_id).get()
    if not snap.exists:
        raise ValidationError("La licencia indicada no existe en el catálogo.")
    data = snap.to_dict() or {}
    data["id"] = snap.id
    if not data.get("active", True):
        raise ValidationError("La licencia indicada se encuentra deshabilitada.")
    data["group_name"] = group_name_for_license(data.get("name", ""))
    group = get_group(data["group_name"])
    if not group:
        raise ValidationError("La licencia no tiene creado su grupo de seguridad. Ejecuta la migración de grupos.")
    data["assigned_count"] = int(group.get("member_count", 0) or 0)
    validate_group_name(data["group_name"])
    return _enrich_with_graph_inventory([data])[0]

def available_stock(lic: dict) -> int:
    return max(int(lic.get("total_stock", 0)) - int(lic.get("assigned_count", 0)), 0)


def user_assignments(email: str):
    email = (email or "").strip().lower()
    validate_corporate_user(email)
    # En la plataforma, tener licencia equivale a pertenecer al grupo de seguridad.
    licenses = _read_license_docs(active_only=True)
    return memberships_for_user(licenses, email)

def license_assignments(license_id: str, limit: int = 2500):
    lic = get_license(license_id)
    rows = list_group_members(lic["group_name"], limit=limit)
    return [{
        "user_email": x.get("user_email"),
        "license_id": license_id,
        "license_name": lic.get("name"),
        "group_name": lic.get("group_name"),
        "source": "Grupo de seguridad",
        "created_at": x.get("created_at"),
    } for x in rows]

def _assignment_doc_id(license_id: str, email: str) -> str:
    safe = email.lower().replace("@", "__at__").replace(".", "_")
    return f"{license_id}__{safe}"


def _simulate_failure_enabled() -> bool:
    return bool(get_system_config().get("simulate_integration_failure", False))


def _simulate_reassignment_failure_enabled() -> bool:
    return bool(get_system_config().get("simulate_reassignment_failure", False))


def _local_assign(actor: dict, target_email: str, lic: dict):
    if _simulate_failure_enabled():
        raise IntegrationError("No se pudo completar la operación debido a un error simulado del servicio de integración.")
    try:
        assign_member(actor.get("email"), target_email, lic)
    except KeyError as e:
        if "DUPLICATE" in str(e):
            raise ValidationError("El usuario ya pertenece al grupo de seguridad y ya cuenta con la licencia.") from e
        raise
    except OverflowError as e:
        raise ValidationError(f"No hay licencias {lic.get('name')} disponibles. No se realizó la asignación.") from e
    except ValueError as e:
        raise ValidationError(str(e)) from e

def _graph_assign(actor: dict, target_email: str, lic: dict):
    if _simulate_failure_enabled():
        raise IntegrationError("Microsoft Graph no se encuentra disponible en el escenario de validación controlado.")
    client = _graph_client_or_error()
    try:
        if client.is_member(target_email, lic["group_name"]):
            raise ValidationError("El usuario ya tiene la licencia asignada; no se generó una duplicidad.")
        changed = client.add_member(target_email, lic["group_name"])
    except ValidationError:
        raise
    except GraphIntegrationError as e:
        raise IntegrationError(str(e)) from e
    try:
        assign_member(actor.get("email"), target_email, lic)
    except Exception as e:
        try:
            if changed.get("changed"):
                client.remove_member(target_email, lic["group_name"])
        except Exception:
            pass
        if isinstance(e, (ValidationError, IntegrationError)):
            raise
        raise IntegrationError(f"La persistencia del grupo falló y se revirtió la membresía externa: {e}") from e

def assign_license(actor: dict, target_email: str, license_id: str):
    action = "ASSIGN"
    _assert_write(actor, action, target_email, license_id)
    lic = None
    try:
        validate_corporate_user(target_email)
        lic = get_license(license_id)
        if _mode() == "graph":
            _graph_assign(actor, target_email, lic)
        else:
            _local_assign(actor, target_email, lic)
        _audit(action, actor.get("email"), target_email, license_id, "SUCCESS", group_name=lic.get("group_name"))
        return f"Licencia {lic['name']} asignada correctamente a {target_email}."
    except PermissionDenied:
        raise
    except ValidationError as e:
        _audit(action, actor.get("email"), target_email, license_id, "REJECTED", str(e), group_name=(lic or {}).get("group_name"))
        raise
    except IntegrationError as e:
        _audit(action, actor.get("email"), target_email, license_id, "ERROR", str(e), group_name=(lic or {}).get("group_name"))
        raise
    except Exception as e:
        _audit(action, actor.get("email"), target_email, license_id, "ERROR", str(e), group_name=(lic or {}).get("group_name"))
        raise IntegrationError(f"No se pudo completar la asignación: {e}") from e


def _local_unassign(actor: dict, target_email: str, lic: dict):
    if _simulate_failure_enabled():
        raise IntegrationError("No se pudo completar la operación debido a un error simulado del servicio de integración.")
    try:
        unassign_member(actor.get("email"), target_email, lic)
    except KeyError as e:
        if "NOT_ASSIGNED" in str(e):
            raise ValidationError("El usuario no pertenece al grupo de seguridad; no posee la licencia y no se realizaron cambios.") from e
        raise
    except ValueError as e:
        raise ValidationError(str(e)) from e

def _graph_unassign(actor: dict, target_email: str, lic: dict):
    if _simulate_failure_enabled():
        raise IntegrationError("Microsoft Graph no se encuentra disponible en el escenario de validación controlado.")
    client = _graph_client_or_error()
    try:
        if not client.is_member(target_email, lic["group_name"]):
            raise ValidationError("La licencia no estaba asignada al usuario; no se realizaron cambios.")
        changed = client.remove_member(target_email, lic["group_name"])
    except ValidationError:
        raise
    except GraphIntegrationError as e:
        raise IntegrationError(str(e)) from e
    try:
        unassign_member(actor.get("email"), target_email, lic)
    except Exception as e:
        try:
            if changed.get("changed"):
                client.add_member(target_email, lic["group_name"])
        except Exception:
            pass
        if isinstance(e, (ValidationError, IntegrationError)):
            raise
        raise IntegrationError(f"La persistencia del grupo falló y se restauró la membresía externa: {e}") from e

def unassign_license(actor: dict, target_email: str, license_id: str):
    action = "UNASSIGN"
    _assert_write(actor, action, target_email, license_id)
    lic = None
    try:
        validate_corporate_user(target_email)
        lic = get_license(license_id)
        if _mode() == "graph":
            _graph_unassign(actor, target_email, lic)
        else:
            _local_unassign(actor, target_email, lic)
        _audit(action, actor.get("email"), target_email, license_id, "SUCCESS", group_name=lic.get("group_name"))
        return f"Licencia {lic['name']} desasignada correctamente de {target_email}."
    except PermissionDenied:
        raise
    except ValidationError as e:
        _audit(action, actor.get("email"), target_email, license_id, "REJECTED", str(e), group_name=(lic or {}).get("group_name"))
        raise
    except IntegrationError as e:
        _audit(action, actor.get("email"), target_email, license_id, "ERROR", str(e), group_name=(lic or {}).get("group_name"))
        raise
    except Exception as e:
        _audit(action, actor.get("email"), target_email, license_id, "ERROR", str(e), group_name=(lic or {}).get("group_name"))
        raise IntegrationError(f"No se pudo completar la desasignación: {e}") from e


def _local_reassign(actor: dict, source_email: str, dest_email: str, lic: dict):
    if _simulate_failure_enabled():
        raise IntegrationError("No se pudo completar la operación porque Firebase/Firestore se encuentra temporalmente no disponible.")
    try:
        reassign_member(
            actor.get("email"), source_email, dest_email, lic,
            fail_midway=_simulate_reassignment_failure_enabled(),
        )
    except KeyError as e:
        msg = str(e)
        if "SOURCE_NOT_ASSIGNED" in msg:
            raise ValidationError("El usuario origen no pertenece al grupo de seguridad; no se realizó la reasignación.") from e
        if "DEST_ALREADY_ASSIGNED" in msg:
            raise ValidationError("El usuario destino ya pertenece al grupo de seguridad y ya cuenta con la licencia.") from e
        raise
    except RuntimeError as e:
        if "SIMULATED_MIDWAY_FAILURE" in str(e):
            raise IntegrationError("Falla simulada al agregar al usuario destino. La transacción fue revertida y el origen conserva la membresía.") from e
        raise
    except ValueError as e:
        raise ValidationError(str(e)) from e

def _graph_reassign(actor: dict, source_email: str, dest_email: str, lic: dict):
    client = _graph_client_or_error()
    try:
        if not client.is_member(source_email, lic["group_name"]):
            raise ValidationError("El usuario origen no posee la licencia; no se realizó la reasignación.")
        if client.is_member(dest_email, lic["group_name"]):
            raise ValidationError("El usuario destino ya posee la licencia; no se realizó la reasignación.")
    except ValidationError:
        raise
    except GraphIntegrationError as e:
        raise IntegrationError(str(e)) from e

    removed_source = False
    added_dest = False
    try:
        removed_source = bool(client.remove_member(source_email, lic["group_name"]).get("changed"))
        if _simulate_failure_enabled():
            raise IntegrationError("Falla simulada al agregar la licencia al usuario destino.")
        added_dest = bool(client.add_member(dest_email, lic["group_name"]).get("changed"))
        reassign_member(actor.get("email"), source_email, dest_email, lic, fail_midway=False)
    except Exception as e:
        rollback_errors = []
        if added_dest:
            try: client.remove_member(dest_email, lic["group_name"])
            except Exception as rb: rollback_errors.append(f"no se pudo retirar destino: {rb}")
        if removed_source:
            try: client.add_member(source_email, lic["group_name"])
            except Exception as rb: rollback_errors.append(f"no se pudo restaurar origen: {rb}")
        detail = str(e)
        detail += (" | ALERTA ROLLBACK: " + "; ".join(rollback_errors)) if rollback_errors else " | Rollback completado: origen restaurado y destino sin membresía."
        if isinstance(e, ValidationError):
            raise
        raise IntegrationError(detail) from e

def reassign_license(actor: dict, source_email: str, dest_email: str, license_id: str):
    action = "REASSIGN"
    _assert_write(actor, action, source_email, license_id)
    lic = None
    op_id = f"{license_id}:{source_email}->{dest_email}"
    try:
        # El destino se valida antes de retirar al origen: CP015.
        validate_corporate_user(source_email)
        validate_corporate_user(dest_email)
        lic = get_license(license_id)
        if _mode() == "graph":
            _graph_reassign(actor, source_email, dest_email, lic)
        else:
            _local_reassign(actor, source_email, dest_email, lic)
        _audit(
            action,
            actor.get("email"),
            source_email,
            license_id,
            "SUCCESS",
            details=f"Origen={source_email}; Destino={dest_email}",
            operation_id=op_id,
            group_name=lic.get("group_name"),
        )
        return f"Licencia {lic['name']} reasignada de {source_email} a {dest_email}."
    except PermissionDenied:
        raise
    except ValidationError as e:
        _audit(
            action,
            actor.get("email"),
            source_email,
            license_id,
            "REJECTED",
            details=f"Origen={source_email}; Destino={dest_email}; Motivo={e}",
            operation_id=op_id,
            group_name=(lic or {}).get("group_name"),
        )
        raise
    except IntegrationError as e:
        _audit(
            action,
            actor.get("email"),
            source_email,
            license_id,
            "ERROR",
            details=f"Origen={source_email}; Destino={dest_email}; {e}",
            operation_id=op_id,
            group_name=(lic or {}).get("group_name"),
        )
        raise
    except Exception as e:
        _audit(
            action,
            actor.get("email"),
            source_email,
            license_id,
            "ERROR",
            details=f"Origen={source_email}; Destino={dest_email}; {e}",
            operation_id=op_id,
            group_name=(lic or {}).get("group_name"),
        )
        raise IntegrationError(f"No se pudo completar la reasignación: {e}") from e


def recent_audit(limit=200):
    q = (
        get_db()
        .collection("audit_logs")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    out = []
    for d in q.stream():
        x = d.to_dict() or {}
        x["id"] = d.id
        out.append(x)
    return out


def upsert_license(license_id: str, values: dict):
    values = dict(values)
    db = get_db()
    current_snap = db.collection("licenses").document(license_id).get()
    current = current_snap.to_dict() if current_snap.exists else {}
    name = str(values.get("name") or current.get("name") or "").strip()
    if not name:
        raise ValidationError("La licencia debe tener un nombre.")
    old_group = current.get("group_name")
    group_name = rename_group_if_needed(
        license_id,
        old_group,
        name,
        active=values.get("active", current.get("active", True)),
    )
    _validate_group_shape(group_name)
    values["group_name"] = group_name
    values["assigned_count"] = group_member_count(group_name, current.get("assigned_count", 0))
    db.collection("licenses").document(license_id).set(values, merge=True)

def set_corporate_user(email: str, values: dict):
    values = dict(values)
    values["email"] = email.lower()
    get_db().collection("corporate_users").document(email.lower()).set(values, merge=True)


def list_app_users(limit: int = 20, include_qa: bool = False):
    """Devuelve cuentas de acceso sin exponer hashes de contraseña."""
    out = []
    for d in get_db().collection("app_users").limit(limit).stream():
        x = d.to_dict() or {}
        if x.get("qa_only", False) and not include_qa:
            continue
        out.append({
            "email": x.get("email", d.id),
            "display_name": x.get("display_name", ""),
            "role": x.get("role", ""),
            "active": x.get("active", True),
            "can_write": x.get("can_write", True),
            "admin_access": x.get("admin_access", x.get("role") == "platform_admin"),
        })
    return sorted(out, key=lambda x: (x.get("role", ""), x.get("email", "")))




def update_app_user_access(email: str, *, active: bool | None = None, can_write: bool | None = None, admin_access: bool | None = None):
    """Actualiza permisos funcionales de una cuenta de acceso sin modificar su rol ni contraseña."""
    email = (email or "").strip().lower()
    if not email:
        raise ValidationError("Debes indicar una cuenta de acceso.")
    values = {"updated_at": firestore.SERVER_TIMESTAMP}
    if active is not None:
        values["active"] = bool(active)
    if can_write is not None:
        values["can_write"] = bool(can_write)
    if admin_access is not None:
        values["admin_access"] = bool(admin_access)
    get_db().collection("app_users").document(email).set(values, merge=True)


def latest_persisted_operation():
    """Devuelve la última operación funcional registrada en auditoría."""
    for row in recent_audit(25):
        if row.get("action") in {"ASSIGN", "UNASSIGN", "REASSIGN", "REASSIGN_BULK"}:
            return row
    return None

def bulk_reassign_license(actor: dict, sources: list[str], destinations: list[str], license_id: str):
    _assert_write(actor, "REASSIGN_BULK", None, license_id)
    if not sources or len(sources) != len(destinations):
        raise ValidationError("Las listas de origen y destino deben tener la misma cantidad de usuarios.")
    if len(sources) > 160:
        raise ValidationError("La reasignación masiva admite hasta 160 pares por ejecución.")
    sources = [x.strip().lower() for x in sources]
    destinations = [x.strip().lower() for x in destinations]
    if len(set(sources)) != len(sources) or len(set(destinations)) != len(destinations):
        raise ValidationError("No se permiten usuarios repetidos dentro del lote.")
    if set(sources) & set(destinations):
        raise ValidationError("Un usuario no puede aparecer como origen y destino en el mismo lote.")

    lic = get_license(license_id)
    for email in sources + destinations:
        validate_corporate_user(email)

    if _mode() == "graph":
        completed = []
        try:
            for source, dest in zip(sources, destinations):
                reassign_license(actor, source, dest, license_id)
                completed.append((source, dest))
        except Exception:
            for source, dest in reversed(completed):
                try:
                    reassign_license(actor, dest, source, license_id)
                except Exception:
                    pass
            raise
    else:
        try:
            bulk_reassign_members(
                actor.get("email"), sources, destinations, lic,
                fail_midway=_simulate_failure_enabled(),
            )
        except KeyError as e:
            msg = str(e)
            if "SOURCE_NOT_ASSIGNED:" in msg:
                raise ValidationError(f"El usuario origen {msg.split(':',1)[1].strip(chr(39))} no posee la licencia seleccionada.") from e
            if "DEST_ALREADY_ASSIGNED:" in msg:
                raise ValidationError(f"El usuario destino {msg.split(':',1)[1].strip(chr(39))} ya posee la licencia seleccionada.") from e
            raise
        except RuntimeError as e:
            raise IntegrationError("Falla simulada durante la reasignación masiva; toda la transacción fue revertida.") from e

        for source, dest in zip(sources, destinations):
            _audit(
                "REASSIGN", actor.get("email"), source, license_id, "SUCCESS",
                details=f"Origen={source}; Destino={dest}; Lote=MASIVO",
                operation_id=f"{license_id}:{source}->{dest}", group_name=lic.get("group_name"),
            )

    return {
        "count": len(sources),
        "license_name": lic.get("name"),
        "message": f"Se completaron {len(sources)} reasignaciones de {lic.get('name')} sin modificar el total asignado.",
    }

def integration_status() -> dict:
    cfg = get_system_config()
    mode = cfg.get("integration_mode", DEFAULT_INTEGRATION_MODE)
    status = {
        "mode": mode,
        "name": cfg.get("integration_name"),
        "configured": True,
        "healthy": True,
        "details": None,
    }
    if mode == "graph":
        status["configured"] = graph_configured()
        status["healthy"] = False
        if not status["configured"]:
            status["details"] = "Faltan credenciales [azure]."
            return status
        try:
            health = get_graph_client().health()
            status["healthy"] = bool(health.get("ok"))
            status["details"] = health
        except Exception as e:
            status["details"] = str(e)
    return status
