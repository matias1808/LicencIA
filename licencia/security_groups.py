from __future__ import annotations

import re
import unicodedata
from firebase_admin import firestore

from .firebase import get_db
from .config import SECURITY_GROUPS_COLLECTION


def _token(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = value.upper().replace("&", "_")
    value = re.sub(r"[^A-Z0-9]+", "_", value).strip("_")
    return re.sub(r"_+", "_", value)


def group_name_for_license(license_name: str) -> str:
    return f"GRP_LICENCIAMS_{_token(license_name)}_USERS"


def member_doc_id(email: str) -> str:
    return (email or "").strip().lower().replace("@", "__at__").replace(".", "_")


def group_ref(group_name: str):
    return get_db().collection(SECURITY_GROUPS_COLLECTION).document(group_name)


def member_ref(group_name: str, email: str):
    return group_ref(group_name).collection("members").document(member_doc_id(email))


def ensure_group(license_id: str, license_name: str, active: bool = True, member_count: int | None = None) -> str:
    name = group_name_for_license(license_name)
    payload = {
        "name": name,
        "license_id": license_id,
        "license_name": license_name,
        "active": bool(active),
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    snap = group_ref(name).get()
    if not snap.exists:
        payload["created_at"] = firestore.SERVER_TIMESTAMP
        payload["member_count"] = int(member_count or 0)
    elif member_count is not None:
        payload["member_count"] = int(member_count)
    group_ref(name).set(payload, merge=True)
    return name


def get_group(group_name: str) -> dict | None:
    snap = group_ref(group_name).get()
    if not snap.exists:
        return None
    out = snap.to_dict() or {}
    out["id"] = snap.id
    return out


def group_member_count(group_name: str, fallback: int = 0) -> int:
    data = get_group(group_name)
    if not data:
        return int(fallback)
    return int(data.get("member_count", fallback) or 0)


def has_member(group_name: str, email: str) -> bool:
    return member_ref(group_name, email).get().exists


def list_members(group_name: str, limit: int = 2500) -> list[dict]:
    rows = []
    for d in group_ref(group_name).collection("members").limit(limit).stream():
        x = d.to_dict() or {}
        x["id"] = d.id
        rows.append(x)
    return rows


def memberships_for_user(licenses: list[dict], email: str) -> list[dict]:
    email = (email or "").strip().lower()
    out = []
    for lic in licenses:
        group_name = lic.get("group_name") or group_name_for_license(lic.get("name", ""))
        snap = member_ref(group_name, email).get()
        if snap.exists:
            out.append({
                "user_email": email,
                "license_id": lic["id"],
                "license_name": lic.get("name"),
                "group_name": group_name,
                "source": "Grupo de seguridad",
            })
    return out


def assign_member(actor_email: str, email: str, lic: dict) -> None:
    db = get_db()
    group_name = lic["group_name"]
    g_ref = db.collection(SECURITY_GROUPS_COLLECTION).document(group_name)
    m_ref = g_ref.collection("members").document(member_doc_id(email))
    l_ref = db.collection("licenses").document(lic["id"])
    tx = db.transaction()

    @firestore.transactional
    def _run(transaction):
        member = m_ref.get(transaction=transaction)
        group = g_ref.get(transaction=transaction)
        license_snap = l_ref.get(transaction=transaction)
        if not group.exists:
            raise ValueError("El grupo de seguridad de la licencia no existe.")
        if member.exists:
            raise KeyError("DUPLICATE")
        ldata = license_snap.to_dict() or {}
        gdata = group.to_dict() or {}
        assigned = int(gdata.get("member_count", 0) or 0)
        total = int(ldata.get("total_stock", 0) or 0)
        if total - assigned <= 0:
            raise OverflowError("NO_STOCK")
        transaction.set(m_ref, {
            "user_email": email.lower(),
            "license_id": lic["id"],
            "license_name": lic.get("name"),
            "group_name": group_name,
            "added_by": actor_email,
            "created_at": firestore.SERVER_TIMESTAMP,
        })
        transaction.update(g_ref, {
            "member_count": firestore.Increment(1),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        transaction.update(l_ref, {"assigned_count": firestore.Increment(1)})

    _run(tx)


def unassign_member(actor_email: str, email: str, lic: dict) -> None:
    db = get_db()
    group_name = lic["group_name"]
    g_ref = db.collection(SECURITY_GROUPS_COLLECTION).document(group_name)
    m_ref = g_ref.collection("members").document(member_doc_id(email))
    l_ref = db.collection("licenses").document(lic["id"])
    tx = db.transaction()

    @firestore.transactional
    def _run(transaction):
        member = m_ref.get(transaction=transaction)
        group = g_ref.get(transaction=transaction)
        license_snap = l_ref.get(transaction=transaction)
        if not group.exists:
            raise ValueError("El grupo de seguridad de la licencia no existe.")
        if not member.exists:
            raise KeyError("NOT_ASSIGNED")
        ldata = license_snap.to_dict() or {}
        gdata = group.to_dict() or {}
        new_count = max(int(gdata.get("member_count", 0) or 0) - 1, 0)
        new_license_count = max(int(ldata.get("assigned_count", 0) or 0) - 1, 0)
        transaction.delete(m_ref)
        transaction.update(g_ref, {"member_count": new_count, "updated_at": firestore.SERVER_TIMESTAMP})
        transaction.update(l_ref, {"assigned_count": new_license_count})

    _run(tx)


def reassign_member(actor_email: str, source_email: str, dest_email: str, lic: dict, fail_midway: bool = False) -> None:
    db = get_db()
    group_name = lic["group_name"]
    g_ref = db.collection(SECURITY_GROUPS_COLLECTION).document(group_name)
    src_ref = g_ref.collection("members").document(member_doc_id(source_email))
    dst_ref = g_ref.collection("members").document(member_doc_id(dest_email))
    tx = db.transaction()

    @firestore.transactional
    def _run(transaction):
        src = src_ref.get(transaction=transaction)
        dst = dst_ref.get(transaction=transaction)
        group = g_ref.get(transaction=transaction)
        if not group.exists:
            raise ValueError("El grupo de seguridad de la licencia no existe.")
        if not src.exists:
            raise KeyError("SOURCE_NOT_ASSIGNED")
        if dst.exists:
            raise KeyError("DEST_ALREADY_ASSIGNED")
        transaction.delete(src_ref)
        if fail_midway:
            raise RuntimeError("SIMULATED_MIDWAY_FAILURE")
        transaction.set(dst_ref, {
            "user_email": dest_email.lower(),
            "license_id": lic["id"],
            "license_name": lic.get("name"),
            "group_name": group_name,
            "added_by": actor_email,
            "created_at": firestore.SERVER_TIMESTAMP,
            "reassigned_from": source_email.lower(),
        })
        transaction.update(g_ref, {"updated_at": firestore.SERVER_TIMESTAMP})

    _run(tx)


def bulk_reassign_members(actor_email: str, sources: list[str], destinations: list[str], lic: dict, fail_midway: bool = False) -> None:
    db = get_db()
    group_name = lic["group_name"]
    g_ref = db.collection(SECURITY_GROUPS_COLLECTION).document(group_name)
    src_refs = [g_ref.collection("members").document(member_doc_id(x)) for x in sources]
    dst_refs = [g_ref.collection("members").document(member_doc_id(x)) for x in destinations]
    tx = db.transaction()

    @firestore.transactional
    def _run(transaction):
        group = g_ref.get(transaction=transaction)
        if not group.exists:
            raise ValueError("El grupo de seguridad de la licencia no existe.")
        for email, ref in zip(sources, src_refs):
            if not ref.get(transaction=transaction).exists:
                raise KeyError(f"SOURCE_NOT_ASSIGNED:{email}")
        for email, ref in zip(destinations, dst_refs):
            if ref.get(transaction=transaction).exists:
                raise KeyError(f"DEST_ALREADY_ASSIGNED:{email}")
        for ref in src_refs:
            transaction.delete(ref)
        if fail_midway:
            raise RuntimeError("SIMULATED_MIDWAY_FAILURE")
        for source, dest, ref in zip(sources, destinations, dst_refs):
            transaction.set(ref, {
                "user_email": dest.lower(),
                "license_id": lic["id"],
                "license_name": lic.get("name"),
                "group_name": group_name,
                "added_by": actor_email,
                "created_at": firestore.SERVER_TIMESTAMP,
                "reassigned_from": source.lower(),
            })
        transaction.update(g_ref, {"updated_at": firestore.SERVER_TIMESTAMP})

    _run(tx)


def rename_group_if_needed(license_id: str, old_group_name: str | None, license_name: str, active: bool = True) -> str:
    new_name = group_name_for_license(license_name)
    if not old_group_name or old_group_name == new_name:
        ensure_group(license_id, license_name, active=active)
        return new_name

    old_ref = group_ref(old_group_name)
    old = old_ref.get()
    if not old.exists:
        ensure_group(license_id, license_name, active=active)
        return new_name

    members = list(old_ref.collection("members").stream())
    ensure_group(license_id, license_name, active=active, member_count=len(members))
    new_ref = group_ref(new_name)
    for i in range(0, len(members), 350):
        batch = get_db().batch()
        for d in members[i:i + 350]:
            data = d.to_dict() or {}
            data["group_name"] = new_name
            data["license_name"] = license_name
            batch.set(new_ref.collection("members").document(d.id), data)
            batch.delete(d.reference)
        batch.commit()
    old_ref.delete()
    return new_name
