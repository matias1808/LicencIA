\
from __future__ import annotations

import re
from typing import Iterable
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .firebase import get_db
from .config import AUTHORIZED_GROUP_PATTERN, DEFAULT_ALLOWED_DOMAINS


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
    "integration_name": "Firebase Connector",
  }
  if snap.exists:
    base.update(snap.to_dict() or {})
  return base


def update_system_config(values: dict):
  get_db().collection("system_config").document("main").set(
    values, merge=True
  )


def corporate_email_allowed(email: str) -> bool:
  email = (email or "").strip().lower()
  cfg = get_system_config()
  return any(email.endswith("@" + d.lower()) for d in cfg.get("allowed_domains", DEFAULT_ALLOWED_DOMAINS))


def get_corporate_user(email: str):
  db = get_db()
  snap = db.collection("corporate_users").document(email.strip().lower()).get()
  return snap.to_dict() if snap.exists else None


def validate_corporate_user(email: str) -> dict:
  if not corporate_email_allowed(email):
    raise ValidationError("El correo no pertenece a un dominio corporativo permitido.")
  user = get_corporate_user(email)
  if not user:
    raise ValidationError("El usuario corporativo no existe en el repositorio cargado.")
  if not user.get("active", True):
    raise ValidationError("El usuario corporativo existe, pero se encuentra deshabilitado.")
  return user


def list_corporate_users(limit: int = 2000):
  db = get_db()
  return [d.to_dict() for d in db.collection("corporate_users").limit(limit).stream()]


def list_licenses(active_only: bool = False):
  db = get_db()
  docs = db.collection("licenses").stream()
  items = []
  for d in docs:
    x = d.to_dict()
    x["id"] = d.id
    if active_only and not x.get("active", True):
      continue
    items.append(x)
  return sorted(items, key=lambda x: x.get("name", ""))


def get_license(license_id: str):
  snap = get_db().collection("licenses").document(license_id).get()
  if not snap.exists:
    raise ValidationError("La licencia indicada no existe en el catálogo.")
  data = snap.to_dict()
  data["id"] = snap.id
  if not data.get("active", True):
    raise ValidationError("La licencia indicada se encuentra deshabilitada.")
  group_name = data.get("group_name", "")
  if not re.match(AUTHORIZED_GROUP_PATTERN, group_name):
    raise ValidationError("La nomenclatura del grupo de seguridad no está autorizada.")
  return data


def available_stock(lic: dict) -> int:
  return max(int(lic.get("total_stock", 0)) - int(lic.get("assigned_count", 0)), 0)


def user_assignments(email: str):
  db = get_db()
  q = db.collection("assignments").where(filter=FieldFilter("user_email", "==", email.lower()))
  out = []
  for d in q.stream():
    x = d.to_dict()
    x["id"] = d.id
    out.append(x)
  return out


def license_assignments(license_id: str, limit: int = 2500):
  db = get_db()
  q = db.collection("assignments").where(filter=FieldFilter("license_id", "==", license_id)).limit(limit)
  return [d.to_dict() for d in q.stream()]


def _assignment_doc_id(license_id: str, email: str) -> str:
  safe = email.lower().replace("@", "__at__").replace(".", "_")
  return f"{license_id}__{safe}"


def _audit(action, actor, target_user, license_id, result, details="", operation_id=None):
  get_db().collection("audit_logs").add({
    "action": action,
    "actor": actor,
    "target_user": target_user,
    "license_id": license_id,
    "result": result,
    "details": details,
    "operation_id": operation_id,
    "created_at": firestore.SERVER_TIMESTAMP,
  })


def _check_integration():
  if get_system_config().get("simulate_integration_failure", False):
    raise IntegrationError("No se pudo completar la operación debido a un error del servicio de integración.")


def assign_license(actor: dict, target_email: str, license_id: str):
  if actor.get("role") not in {"license_manager", "platform_admin"}:
    _audit("ASSIGN", actor.get("email"), target_email, license_id, "DENIED", "Permisos insuficientes")
    raise PermissionDenied("No tienes permisos para modificar licencias. La operación fue bloqueada.")

  validate_corporate_user(target_email)
  lic = get_license(license_id)
  _check_integration()

  db = get_db()
  assignment_ref = db.collection("assignments").document(_assignment_doc_id(license_id, target_email))
  license_ref = db.collection("licenses").document(license_id)
  tx = db.transaction()

  @firestore.transactional
  def _run(transaction):
    a = assignment_ref.get(transaction=transaction)
    if a.exists:
      raise ValidationError("El usuario ya tiene la licencia asignada; no se generó una duplicidad.")
    l = license_ref.get(transaction=transaction).to_dict()
    avail = int(l.get("total_stock", 0)) - int(l.get("assigned_count", 0))
    if avail <= 0:
      raise ValidationError(f"No hay licencias {l.get('name')} disponibles. No se realizó la asignación.")
    transaction.set(assignment_ref, {
      "user_email": target_email.lower(),
      "license_id": license_id,
      "license_name": l.get("name"),
      "group_name": l.get("group_name"),
      "assigned_by": actor.get("email"),
      "created_at": firestore.SERVER_TIMESTAMP,
    })
    transaction.update(license_ref, {"assigned_count": firestore.Increment(1)})

  try:
    _run(tx)
    _audit("ASSIGN", actor.get("email"), target_email, license_id, "SUCCESS")
    return f"Licencia {lic['name']} asignada correctamente a {target_email}."
  except LicencIAError:
    raise
  except Exception as e:
    _audit("ASSIGN", actor.get("email"), target_email, license_id, "ERROR", str(e))
    raise


def unassign_license(actor: dict, target_email: str, license_id: str):
  if actor.get("role") not in {"license_manager", "platform_admin"}:
    _audit("UNASSIGN", actor.get("email"), target_email, license_id, "DENIED", "Permisos insuficientes")
    raise PermissionDenied("No tienes permisos para modificar licencias. La operación fue bloqueada.")

  validate_corporate_user(target_email)
  lic = get_license(license_id)
  _check_integration()

  db = get_db()
  assignment_ref = db.collection("assignments").document(_assignment_doc_id(license_id, target_email))
  license_ref = db.collection("licenses").document(license_id)
  tx = db.transaction()

  @firestore.transactional
  def _run(transaction):
    a = assignment_ref.get(transaction=transaction)
    if not a.exists:
      raise ValidationError("La licencia no estaba asignada al usuario; no se realizaron cambios.")
    transaction.delete(assignment_ref)
    transaction.update(license_ref, {"assigned_count": firestore.Increment(-1)})

  try:
    _run(tx)
    _audit("UNASSIGN", actor.get("email"), target_email, license_id, "SUCCESS")
    return f"Licencia {lic['name']} desasignada correctamente de {target_email}."
  except LicencIAError:
    raise
  except Exception as e:
    _audit("UNASSIGN", actor.get("email"), target_email, license_id, "ERROR", str(e))
    raise


def reassign_license(actor: dict, source_email: str, dest_email: str, license_id: str):
  if actor.get("role") not in {"license_manager", "platform_admin"}:
    _audit("REASSIGN", actor.get("email"), source_email, license_id, "DENIED", "Permisos insuficientes")
    raise PermissionDenied("No tienes permisos para modificar licencias. La operación fue bloqueada.")

  validate_corporate_user(source_email)
  validate_corporate_user(dest_email)
  lic = get_license(license_id)
  _check_integration()

  db = get_db()
  src_ref = db.collection("assignments").document(_assignment_doc_id(license_id, source_email))
  dst_ref = db.collection("assignments").document(_assignment_doc_id(license_id, dest_email))
  tx = db.transaction()

  @firestore.transactional
  def _run(transaction):
    src = src_ref.get(transaction=transaction)
    dst = dst_ref.get(transaction=transaction)
    if not src.exists:
      raise ValidationError("El usuario origen no posee la licencia; no se realizó la reasignación.")
    if dst.exists:
      raise ValidationError("El usuario destino ya posee la licencia; no se realizó la reasignación.")
    transaction.delete(src_ref)
    transaction.set(dst_ref, {
      "user_email": dest_email.lower(),
      "license_id": license_id,
      "license_name": lic.get("name"),
      "group_name": lic.get("group_name"),
      "assigned_by": actor.get("email"),
      "created_at": firestore.SERVER_TIMESTAMP,
    })

  try:
    _run(tx)
    op_id = f"{license_id}:{source_email}->{dest_email}"
    _audit(
      "REASSIGN",
      actor.get("email"),
      source_email,
      license_id,
      "SUCCESS",
      details=f"Origen={source_email}; Destino={dest_email}",
      operation_id=op_id,
    )
    return f"Licencia {lic['name']} reasignada de {source_email} a {dest_email}."
  except LicencIAError:
    raise
  except Exception as e:
    _audit("REASSIGN", actor.get("email"), source_email, license_id, "ERROR", str(e))
    raise


def recent_audit(limit=200):
  db = get_db()
  q = db.collection("audit_logs").order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
  out = []
  for d in q.stream():
    x = d.to_dict()
    x["id"] = d.id
    out.append(x)
  return out


def upsert_license(license_id: str, values: dict):
  get_db().collection("licenses").document(license_id).set(values, merge=True)


def set_corporate_user(email: str, values: dict):
  values = dict(values)
  values["email"] = email.lower()
  get_db().collection("corporate_users").document(email.lower()).set(values, merge=True)


def list_app_users(limit: int = 20):
  """Return access accounts without password hashes."""
  db = get_db()
  out = []
  for d in db.collection("app_users").limit(limit).stream():
    x = d.to_dict() or {}
    out.append({
      "email": x.get("email", d.id),
      "display_name": x.get("display_name", ""),
      "role": x.get("role", ""),
      "active": x.get("active", True),
    })
  return sorted(out, key=lambda x: x.get("role", ""))



def bulk_reassign_license(actor: dict, sources: list[str], destinations: list[str], license_id: str):
  """Atomically reassign one license across many users without changing assigned_count."""
  if actor.get("role") not in {"license_manager", "platform_admin"}:
    raise PermissionDenied("No tienes permisos para modificar licencias.")
  if not sources or len(sources) != len(destinations):
    raise ValidationError("Las listas de origen y destino deben tener la misma cantidad de usuarios.")
  if len(sources) > 160:
    raise ValidationError("La reasignación masiva admite hasta 160 pares por ejecución.")
  if len(set(sources)) != len(sources) or len(set(destinations)) != len(destinations):
    raise ValidationError("No se permiten usuarios repetidos dentro del lote.")
  if set(sources) & set(destinations):
    raise ValidationError("Un usuario no puede aparecer como origen y destino en el mismo lote.")

  lic = get_license(license_id)
  _check_integration()
  for email in sources + destinations:
    validate_corporate_user(email)

  db = get_db()
  tx = db.transaction()

  @firestore.transactional
  def _run(transaction):
    source_refs = [db.collection("assignments").document(_assignment_doc_id(license_id, e)) for e in sources]
    dest_refs = [db.collection("assignments").document(_assignment_doc_id(license_id, e)) for e in destinations]

    for email, ref in zip(sources, source_refs):
      snap = ref.get(transaction=transaction)
      if not snap.exists:
        raise ValidationError(f"El usuario origen {email} no posee la licencia seleccionada.")
    for email, ref in zip(destinations, dest_refs):
      snap = ref.get(transaction=transaction)
      if snap.exists:
        raise ValidationError(f"El usuario destino {email} ya posee la licencia seleccionada.")

    # Fase lógica 1: retirar todos los orígenes.
    for ref in source_refs:
      transaction.delete(ref)

    # Fase lógica 2: agregar todos los destinos.
    for email, ref in zip(destinations, dest_refs):
      transaction.set(ref, {
        "user_email": email.lower(),
        "license_id": license_id,
        "license_name": lic.get("name"),
        "group_name": lic.get("group_name"),
        "assigned_by": actor.get("email"),
        "created_at": firestore.SERVER_TIMESTAMP,
      })

    # Una evidencia por par, dentro de la misma transacción.
    for source, dest in zip(sources, destinations):
      audit_ref = db.collection("audit_logs").document()
      transaction.set(audit_ref, {
        "action": "REASSIGN",
        "actor": actor.get("email"),
        "target_user": source,
        "license_id": license_id,
        "result": "SUCCESS",
        "details": f"Origen={source}; Destino={dest}; Lote=MASIVO",
        "operation_id": f"{license_id}:{source}->{dest}",
        "created_at": firestore.SERVER_TIMESTAMP,
      })

  _run(tx)
  return {
    "count": len(sources),
    "license_name": lic.get("name"),
    "message": f"Se completaron {len(sources)} reasignaciones de {lic.get('name')} sin modificar el total asignado.",
  }
