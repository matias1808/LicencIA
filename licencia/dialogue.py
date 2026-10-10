from __future__ import annotations

ACTION_INTENTS={"assign","unassign","reassign","user_licenses"}


def start_pending(result):
  p={"intent":result.intent,"license_id":result.license_id,"license_name":result.license_name}
  if result.intent in {"assign","unassign","user_licenses"}:
    p["target"]=result.emails[0] if result.emails else None
  elif result.intent=="reassign":
    p["source"]=result.emails[0] if len(result.emails)>0 else None
    p["dest"]=result.emails[1] if len(result.emails)>1 else None
  return p


def merge_pending(p,result):
  p=dict(p)
  if result.license_id:
    p["license_id"]=result.license_id
    p["license_name"]=result.license_name
  if p["intent"] in {"assign","unassign","user_licenses"} and result.emails:
    p["target"]=result.emails[0]
  elif p["intent"]=="reassign":
    existing=[p.get("source"),p.get("dest")]
    incoming=result.emails
    vals=[x for x in existing if x]
    for x in incoming:
      if x not in vals:
        vals.append(x)
    p["source"]=vals[0] if len(vals)>0 else None
    p["dest"]=vals[1] if len(vals)>1 else None
  return p


def missing_slots(p):
  miss=[]
  if p["intent"] in {"assign","unassign","reassign"} and not p.get("license_id"):
    miss.append("license")
  if p["intent"] in {"assign","unassign","user_licenses"} and not p.get("target"):
    miss.append("target")
  if p["intent"]=="reassign":
    if not p.get("source"):
      miss.append("source")
    if not p.get("dest"):
      miss.append("dest")
  return miss


def next_question(p):
  miss=missing_slots(p)
  if not miss:
    return None
  if "license" in miss:
    return "Perfecto. ¿Qué licencia deseas gestionar? Puedes escribir, por ejemplo, **M365 E3**, **Power BI** o **Visio P2**."
  if "target" in miss:
    return "Ya tengo la operación. Ahora indícame el **correo corporativo del usuario**."
  if "source" in miss:
    return "Indícame el **correo corporativo del usuario origen** que actualmente tiene la licencia."
  if "dest" in miss:
    return "¿A qué **usuario destino** deseas transferir la licencia?"
  return "Necesito un dato adicional para continuar."


def summary(p):
  if p["intent"]=="assign":
    return f"Asignar **{p['license_name']}** a **{p['target']}**"
  if p["intent"]=="unassign":
    return f"Desasignar **{p['license_name']}** de **{p['target']}**"
  if p["intent"]=="reassign":
    return f"Reasignar **{p['license_name']}** de **{p['source']}** a **{p['dest']}**"
  if p["intent"]=="user_licenses":
    return f"Consultar licencias de **{p['target']}**"
  return ""


def pending_label(p):
  if not p:
    return ""
  labels={
    "assign":"Asignación",
    "unassign":"Desasignación",
    "reassign":"Reasignación",
    "user_licenses":"Consulta de usuario",
  }
  base=labels.get(p.get("intent"), "Solicitud")
  details=[]
  if p.get("license_name"):
    details.append(p["license_name"])
  if p.get("target"):
    details.append(p["target"])
  if p.get("source"):
    details.append(f"origen: {p['source']}")
  if p.get("dest"):
    details.append(f"destino: {p['dest']}")
  return base + (" · " + " · ".join(details) if details else "")
