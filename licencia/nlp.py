from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass
import joblib
import streamlit as st
from rapidfuzz import fuzz
from .repository import list_licenses

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

LICENSE_ALIASES = {
    "M365 E5 Unified": ["m365 e5","microsoft 365 e5","e5 unified","e5"],
    "M365 F3 FUSL": ["m365 f3","microsoft 365 f3","f3 fusl","f3"],
    "M365 E3": ["m365 e3","microsoft 365 e3","e3"],
    "EOA Exchange Online": ["eoa exchange online","exchange online","eoa"],
    "Exchange Kiosk": ["exchange kiosk","kiosk"],
    "Exchange P1": ["exchange p1","p1"],
    "Exchange P2": ["exchange p2","p2"],
    "Planner & Project P3": ["planner & project p3","planner y project p3","project p3","p3"],
    "Power Apps Premium": ["power apps premium","power apps"],
    "Power Automate Premium": ["power automate premium","power automate"],
    "Power BI Premium USL": ["power bi premium usl","power bi premium","powerbi","power bi"],
    "Visio P2": ["visio p2","visio plan 2","visio"],
    "W365 Ent 4vCPU/16GB/128GB": ["w365 ent 4vcpu/16gb/128gb","windows 365 enterprise","windows 365","cloud pc","w365"],
}

@dataclass
class NLPResult:
    intent: str
    confidence: float
    emails: list[str]
    license_id: str | None
    license_name: str | None
    missing: list[str]

@st.cache_data(ttl=300, show_spinner=False)
def _cached_licenses():
    return list_licenses(active_only=True)


@st.cache_resource(show_spinner=False)
def load_intent_model():
    p=Path(__file__).resolve().parents[1]/"models"/"intent_model_v4.joblib"
    if not p.exists():
        raise RuntimeError("Falta models/intent_model_v4.joblib")
    return joblib.load(p)


def _normalize(text:str)->str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _rule_hint(text:str)->str|None:
    t=_normalize(text)

    # Quiénes poseen una licencia / cantidad de usuarios por licencia.
    holder_patterns=[
        "quienes tienen", "quiénes tienen", "que usuarios tienen", "qué usuarios tienen",
        "usuarios con ", "usuarios que tienen", "usuarios que usan", "quienes usan", "quiénes usan",
        "lista de usuarios con", "listar usuarios con", "usuarios asignados a",
        "a quiénes se asignó", "a quienes se asigno", "quien tiene ", "quién tiene ",
        "cuantos usuarios tienen", "cuántos usuarios tienen", "cuantos tienen", "cuántos tienen",
        "personas con ", "usuarios de la licencia"
    ]
    if any(x in t for x in holder_patterns):
        return "license_holders"

    # Reasignar debe evaluarse antes de asignar/desasignar.
    if (
        any(x in t for x in [
            "reasigna","reasignar","reasignr","transfiere","transferir","traslada","migrar","traspasa",
            "herede","cambia el propietario","cambia el titular","nuevo titular","debe pasar a","en lugar de",
            "mueve la licencia", "pasa la licencia", "pasar la licencia"
        ])
        or ("quita" in t and ("dásela" in t or "dasela" in t))
        or ("retira" in t and ("asigna" in t or "dale" in t))
    ):
        return "reassign"

    if any(x in t for x in [
        "desasigna","desasignar","desasignr","retira","retirar","quita","quitar","quítale","revoca",
        "remueve","dar de baja","libera","deshabilita","desvincula","pierda el acceso","recupera la licencia",
        "sácale", "sacale", "elimina la licencia"
    ]):
        return "unassign"

    if any(x in t for x in [
        "asigna","asignar","asignr","dale","otorga","habilita","activa","provisiona","concede","dar acceso",
        "incorpora","deja operativo","quede licenciado","necesito darle", "ponle", "agrega la licencia"
    ]):
        return "assign"

    if any(x in t for x in [
        "qué licencias tiene","que licencias tiene","qué tiene asignado","que tiene asignado","licenciamiento de",
        "suscripciones de","accesos licenciados","productos están vinculados","productos estan vinculados",
        "servicios licenciados", "licencias del usuario", "licencias asignadas a"
    ]):
        return "user_licenses"

    if any(x in t for x in [
        "inventario","stock","disponibilidad","cuántas quedan","cuantas quedan","cuántas hay disponibles",
        "cuantas hay disponibles","cupos","saldo de","capacidad libre","ocupación actual","ocupacion actual",
        "capacidad de","disponibles", "cuanto stock", "cuánto stock", "licencias libres"
    ]):
        return "inventory"

    if any(x in t for x in [
        "auditoría","auditoria","historial","trazabilidad","log de licencias","quién hizo","quien hizo",
        "registro histórico","registro historico","rastro de operaciones","registro de actividad"
    ]):
        return "audit"

    if any(x in t for x in [
        "qué licencias manejas","que licencias manejas","qué licencias soportas","que licencias soportas",
        "catálogo","catalogo","qué productos puedo gestionar","qué licencias reconoce","que licencias reconoce",
        "productos están cargados","productos estan cargados", "qué licencias hay", "que licencias hay"
    ]):
        return "catalog"

    if any(x in t for x in ["cómo estás","como estas","cómo te va","como te va","cómo andas","como andas","todo bien"]):
        return "wellbeing"
    if any(x in t for x in ["gracias","te agradezco","muy amable","buenazo","perfecto gracias"]):
        return "thanks"
    if any(x in t for x in [
        "qué puedes hacer","que puedes hacer","qué funciones tienes","que funciones tienes","para qué sirves",
        "para que sirves","qué operaciones soportas","que operaciones soportas","ayuda","help","quien eres",
        "quién eres","qué hago aquí","que hago aqui"
    ]):
        return "capabilities"
    if any(x in t for x in ["adiós","adios","chau","hasta luego","nos vemos","bye","eso es todo"]):
        return "farewell"
    if any(x in t for x in ["hola","buenos días","buenos dias","buenas tardes","buenas noches","buen día","buen dia","hey","buenas"]):
        return "greeting"

    # Fuera de alcance conocido. No intentamos responder conocimiento general.
    if any(x in t for x in [
        "guerra","historia del perú","historia del peru","miguel grau","independencia","presidente","elecciones",
        "clima","noticias","partido","receta","película","pelicula","vuelos","hotel","dólar","dolar","poema",
        "integral","canción","cancion","google","internet","restaurante","fotosíntesis","fotosintesis","capital de",
        "física","fisica","periquito","animal","deporte","futbol","fútbol"
    ]):
        return "out_of_scope"
    return None


def _find_license(text:str):
    t=_normalize(text).replace("powerbi","power bi")
    licenses=_cached_licenses()
    hits=[]
    for lic in licenses:
        aliases=LICENSE_ALIASES.get(lic.get("name",""),[])
        for alias in aliases:
            a=alias.lower().replace("powerbi","power bi")
            # For short aliases E3/E5/F3/P1/P2/P3 require word boundaries.
            if len(a) <= 3:
                if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", t):
                    hits.append((len(a),lic))
            elif a in t:
                hits.append((len(a),lic))
    if hits:
        return max(hits,key=lambda x:x[0])[1]

    best=None; score=0
    for lic in licenses:
        for c in [lic.get("name",""),lic.get("sku",""),lic.get("group_name","")]:
            c=str(c).lower().replace("powerbi","power bi")
            if not c:
                continue
            s=fuzz.partial_ratio(c,t)
            if s>score:
                best,score=lic,s
    return best if score>=82 else None


def _has_action_domain_signal(text: str, emails: list[str], lic) -> bool:
    t = _normalize(text)
    action_words = [
        "asigna", "asignar", "dale", "otorga", "habilita", "activa", "provisiona", "concede", "ponle",
        "desasigna", "desasignar", "retira", "retirar", "quita", "quitar", "quítale", "revoca", "remueve",
        "libera", "deshabilita", "reasigna", "reasignar", "transfiere", "transferir", "traslada", "traspasa",
        "migrar", "cambia el titular", "nuevo titular", "licencia", "licenciamiento"
    ]
    return bool(emails or lic or any(w in t for w in action_words))


def parse_message(text:str)->NLPResult:
    model=load_intent_model()
    probs=model.predict_proba([text])[0]
    i=probs.argmax()
    intent=str(model.classes_[i])
    confidence=float(probs[i])

    emails=list(dict.fromkeys(x.lower() for x in EMAIL_RE.findall(text)))
    lic=_find_license(text)

    hint=_rule_hint(text)
    if hint:
        intent=hint
        confidence=max(confidence,.99)
    elif confidence < .48:
        intent="ambiguous"

    # Sensitive actions require domain evidence. A random phrase cannot open a change request.
    if intent in {"assign","unassign","reassign"} and not _has_action_domain_signal(text, emails, lic):
        intent="ambiguous"
        confidence=min(confidence, .50)

    # Generic model guesses without entities are treated conservatively.
    if intent == "user_licenses" and not emails and not hint:
        intent="ambiguous"
    if intent == "license_holders" and not lic:
        confidence=min(confidence, .65)

    missing=[]
    if intent in {"assign","unassign"}:
        if not lic:
            missing.append("licencia")
        if not emails:
            missing.append("usuario")
    elif intent=="reassign":
        if not lic:
            missing.append("licencia")
        if len(emails)<2:
            missing.append("usuario origen y/o destino")
    elif intent=="user_licenses" and not emails:
        missing.append("usuario")
    elif intent=="license_holders" and not lic:
        missing.append("licencia")

    return NLPResult(
        intent=intent,
        confidence=confidence,
        emails=emails,
        license_id=lic.get("id") if lic else None,
        license_name=lic.get("name") if lic else None,
        missing=missing
    )
