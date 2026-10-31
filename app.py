from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from licencia.config import (
  APP_NAME, ROLE_LABELS, WRITE_ROLES, AUDIT_ROLES, METRICS_ROLES, CONFIG_ROLES,
  INTENT_LABELS, MAX_BULK_OPERATIONS, MAX_BULK_REASSIGNMENTS,
)
from licencia.auth import authenticate
from licencia.repository import (
  LicencIAError,
  list_licenses, available_stock, user_assignments, validate_corporate_user,
  assign_license, unassign_license, reassign_license, bulk_reassign_license, recent_audit,
  update_system_config, get_system_config, upsert_license, set_corporate_user,
  list_corporate_users, license_assignments, list_app_users,
  update_app_user_access, latest_persisted_operation,
)
from licencia.nlp import parse_message
from licencia.dialogue import start_pending, merge_pending, next_question, summary, pending_label
from licencia.metrics import (
  record_prediction, validate_event, list_events, compute_metrics, compute_baseline_metrics,
)

st.set_page_config(page_title=APP_NAME, page_icon="✦", layout="wide", initial_sidebar_state="expanded")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "m365_logo.png"

def load_logo_data_uri() -> str:
  if LOGO_PATH.exists():
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"
  return ""


def brand_logo_html(size: int = 44, css_class: str = "brand-image") -> str:
  uri = load_logo_data_uri()
  if uri:
    return f'<img src="{uri}" class="{css_class}" width="{size}" height="{size}" />'
  return '<div class="brand-fallback">M365</div>'



def inject_styles():
  st.markdown(
    """
    <style>
    :root{
      --bg:#07101D; --bg2:#0A1422; --panel:#0D1828; --panel2:#101D30;
      --stroke:rgba(148,176,210,.13); --text:#F3F7FD; --muted:#8FA2BA;
      --teal:#35D0BA; --cyan:#55B8FF; --blue:#4A7BFF; --danger:#FF6B7A;
      --shadow:0 24px 60px rgba(0,0,0,.22);
    }
    html, body, [data-testid="stAppViewContainer"], .stApp{
      background:
        radial-gradient(circle at 12% 0%, rgba(53,208,186,.09), transparent 27%),
        radial-gradient(circle at 88% 4%, rgba(74,123,255,.10), transparent 30%),
        linear-gradient(180deg,#07101D 0%,#081321 42%,#07101D 100%) !important;
      color:var(--text);
    }
    [data-testid="stHeader"]{background:rgba(7,16,29,.72); backdrop-filter:blur(14px);}
    [data-testid="stSidebar"]{
      background:linear-gradient(180deg,#091525 0%,#07111E 100%) !important;
      border-right:1px solid var(--stroke);
    }
    [data-testid="stSidebarContent"]{padding:1.15rem .95rem 1.4rem .95rem;}
    .block-container{max-width:1380px;padding-top:1.35rem;padding-bottom:2.6rem;padding-left:2.35rem;padding-right:2.35rem;}
    .premium-hero{
      position:relative; overflow:hidden; padding:1.35rem 1.45rem 1.2rem;
      border:1px solid var(--stroke); border-radius:24px;
      background:linear-gradient(135deg,rgba(15,29,48,.98),rgba(10,24,41,.96));
      box-shadow:var(--shadow); margin-bottom:1rem;
    }
    .premium-hero:after{
      content:""; position:absolute; width:260px;height:260px;right:-85px;top:-120px;border-radius:50%;
      background:radial-gradient(circle,rgba(53,208,186,.22),rgba(74,123,255,.06) 56%,transparent 72%);
    }
    .premium-title{font-size:2rem;font-weight:850;letter-spacing:-.035em;margin:0;color:#F7FBFF;}
    .premium-sub{margin-top:.35rem;color:var(--muted);font-size:.95rem;max-width:900px;line-height:1.5;}
    .status-row{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.9rem;}
    .status-pill{display:inline-flex;align-items:center;gap:.4rem;padding:.34rem .68rem;border-radius:999px;
      background:rgba(255,255,255,.035);border:1px solid var(--stroke);font-size:.78rem;color:#C8D6E8;}
    .status-dot{width:7px;height:7px;border-radius:50%;background:var(--teal);box-shadow:0 0 14px rgba(53,208,186,.7);}
    .glass-card{background:linear-gradient(180deg,rgba(14,26,43,.94),rgba(10,20,35,.94));
      border:1px solid var(--stroke);border-radius:20px;padding:1rem 1.05rem;box-shadow:0 16px 42px rgba(0,0,0,.14);}
    .section-wrap{background:linear-gradient(180deg,rgba(14,26,43,.88),rgba(10,20,35,.88));border:1px solid var(--stroke);
      border-radius:20px;padding:1rem 1.1rem;margin-bottom:.9rem;}
    .section-title{font-size:1.18rem;font-weight:780;color:#F5F9FF;margin:0;}
    .section-help{font-size:.9rem;color:var(--muted);margin-top:.25rem;line-height:1.45;}
    .kpi-card{background:linear-gradient(180deg,rgba(16,30,50,.98),rgba(10,22,38,.98));border:1px solid var(--stroke);
      border-radius:19px;padding:.92rem 1rem;min-height:105px;box-shadow:0 16px 38px rgba(0,0,0,.13);}
    .kpi-label{font-size:.77rem;text-transform:uppercase;letter-spacing:.07em;color:#7F94AE;font-weight:700;}
    .kpi-value{font-size:1.48rem;font-weight:820;color:#F5FAFF;margin-top:.25rem;letter-spacing:-.02em;}
    .kpi-help{font-size:.78rem;color:#8194AA;margin-top:.18rem;}
    .sidebar-brand{padding:1.1rem 1.05rem 1rem 1.05rem;border:1px solid var(--stroke);border-radius:20px;
      background:linear-gradient(145deg,rgba(18,37,60,.96),rgba(9,27,44,.96));margin-bottom:1.05rem;box-shadow:0 18px 45px rgba(0,0,0,.18);}
    .brand-logo-wrap{display:flex;align-items:center;justify-content:flex-start;margin-bottom:.8rem;}
    .brand-image,.login-logo-img{display:block;object-fit:contain;filter:drop-shadow(0 8px 16px rgba(0,0,0,.28));}
    .brand-fallback{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,var(--teal),var(--blue));display:flex;align-items:center;justify-content:center;color:#06101C;font-weight:900;font-size:.72rem;}
    .sidebar-title{font-size:1.26rem;font-weight:830;color:#F7FBFF;margin:0;}.sidebar-sub{font-size:.8rem;color:#8FA2BA;margin-top:.28rem;line-height:1.35;}
    .user-chip{display:inline-flex;align-items:center;gap:.45rem;padding:.36rem .65rem;border-radius:999px;
      background:rgba(53,208,186,.08);border:1px solid rgba(53,208,186,.18);color:#CFF9F2;font-size:.78rem;font-weight:700;}
    .quick-help{background:linear-gradient(180deg,rgba(13,25,42,.90),rgba(9,19,33,.92));border:1px solid var(--stroke);
      border-radius:18px;padding:.85rem .95rem;color:#B8C7D9;font-size:.86rem;line-height:1.65;margin-bottom:.75rem;}
    .pending-banner{background:linear-gradient(90deg,rgba(53,208,186,.10),rgba(74,123,255,.08));border:1px solid rgba(53,208,186,.18);
      border-radius:16px;padding:.72rem .9rem;margin-bottom:.75rem;color:#D8F7F2;font-size:.86rem;}
    div[data-testid="stChatMessage"]{background:rgba(10,20,34,.62);border:1px solid rgba(148,176,210,.09);
      border-radius:18px;padding:.1rem .35rem;margin-bottom:.45rem;}
    div[data-testid="stChatMessage"] p{line-height:1.55;}
    div[data-testid="stDataFrame"]{border:1px solid var(--stroke);border-radius:16px;overflow:hidden;background:#0A1422;}
    div[data-testid="stMetric"]{background:linear-gradient(180deg,rgba(16,30,50,.98),rgba(10,22,38,.98));border:1px solid var(--stroke);
      border-radius:18px;padding:.55rem .8rem;box-shadow:0 14px 34px rgba(0,0,0,.11);}
    .stButton>button, .stDownloadButton>button{border-radius:13px !important;border:1px solid rgba(148,176,210,.16) !important;
      background:linear-gradient(180deg,#101E31,#0B1727) !important;color:#EAF2FC !important;min-height:42px;}
    .stButton>button:hover, .stDownloadButton>button:hover{border-color:rgba(53,208,186,.55) !important;color:#D8FFF9 !important;box-shadow:0 0 0 1px rgba(53,208,186,.14);}
    button[kind="primary"]{background:linear-gradient(135deg,#2EC8B3,#3E83FF) !important;border:none !important;color:#06111D !important;font-weight:800 !important;}
    [data-testid="stChatInput"]{border-top:1px solid rgba(148,176,210,.10);background:rgba(7,16,29,.88);backdrop-filter:blur(12px);}
    [data-testid="stChatInput"] textarea{background:#0D1929 !important;color:#F4F8FD !important;border:1px solid rgba(148,176,210,.14) !important;border-radius:16px !important;}
    input, textarea, [data-baseweb="select"]>div{background-color:#0D1929 !important;color:#EFF5FC !important;border-color:rgba(148,176,210,.14) !important;}
    .login-shell{margin-top:6vh;padding:1.7rem 1.55rem 1.35rem;border:1px solid var(--stroke);border-radius:24px;
      background:linear-gradient(180deg,rgba(13,25,42,.96),rgba(8,18,31,.97));box-shadow:var(--shadow);}
    .login-logo-wrap{margin-bottom:1rem;display:flex;align-items:center;justify-content:flex-start;}
    .login-logo-img{width:64px;height:64px;object-fit:contain;display:block;filter:drop-shadow(0 10px 20px rgba(0,0,0,.28));}
    .small-muted{font-size:.78rem;color:#7F93AA;}
    hr{border-color:rgba(148,176,210,.10) !important;}

    /* Layout spacing */
    [data-testid="stHorizontalBlock"]{gap:1.18rem !important;}
    .stRadio [role="radiogroup"]{gap:.28rem !important;}
    .stRadio [role="radiogroup"] > label{padding:.42rem .48rem !important;border-radius:11px !important;margin:.08rem 0 !important;}
    .stRadio [role="radiogroup"] > label:hover{background:rgba(85,184,255,.055) !important;}
    [data-testid="stSidebar"] .stRadio{margin-top:.62rem;}
    [data-testid="stSidebar"] .stRadio label p{line-height:1.25;}
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > div{margin-bottom:.12rem;}
    [data-testid="stSidebar"] hr{margin:1.15rem 0 !important;}
    .element-container{margin-bottom:.38rem;}
    div[data-testid="stForm"]{border:1px solid var(--stroke);border-radius:18px;padding:1rem 1.05rem;background:rgba(10,20,34,.36);}
    </style>
    """,
    unsafe_allow_html=True,
  )
  try:
    ui_cfg=get_system_config()
  except Exception:
    ui_cfg={}
  palettes={
    "cyan_blue":("#35D0BA","#55B8FF","#4A7BFF"),
    "blue_violet":("#5BB8FF","#7B8CFF","#9B72FF"),
    "green_blue":("#42D39B","#4CC9F0","#3A86FF"),
  }
  teal,cyan,blue=palettes.get(ui_cfg.get("ui_preset","cyan_blue"),palettes["cyan_blue"])
  density=ui_cfg.get("ui_density","comfortable")
  compact_css=".block-container{padding-top:.72rem !important}.section-wrap{margin-bottom:.62rem !important}.kpi-card{min-height:92px !important}" if density=="compact" else ""
  st.markdown(f"<style>:root{{--teal:{teal};--cyan:{cyan};--blue:{blue};}}{compact_css}</style>",unsafe_allow_html=True)


def section_intro(title: str, description: str):
  st.markdown(f"<div class='section-wrap'><div class='section-title'>{title}</div><div class='section-help'>{description}</div></div>", unsafe_allow_html=True)


def kpi_card(label: str, value: str, help_text: str = ""):
  st.markdown(f"<div class='kpi-card'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div><div class='kpi-help'>{help_text}</div></div>", unsafe_allow_html=True)


def logout():
  for key in list(st.session_state.keys()):
    del st.session_state[key]
  st.rerun()


def require_login():
  if "user" in st.session_state:
    return st.session_state["user"]
  left, center, right = st.columns([1.2,1.05,1.2])
  with center:
    st.markdown(f"<div class='login-shell'><div class='login-logo-wrap'>{brand_logo_html(64, 'login-logo-img')}</div><div class='premium-title' style='font-size:1.85rem'>LicencIA</div><div class='premium-sub'>Gestión inteligente, segura y trazable de licencias tecnológicas.</div>", unsafe_allow_html=True)
    with st.form("login_form"):
      email=st.text_input("Correo corporativo",placeholder="usuario@empresas.com.pe")
      password=st.text_input("Contraseña",type="password")
      submit=st.form_submit_button("Ingresar",use_container_width=True,type="primary")
    st.markdown("<div class='small-muted'>Acceso restringido a usuarios autorizados.</div></div>", unsafe_allow_html=True)
  if submit:
    try:
      user=authenticate(email,password)
    except Exception as e:
      st.error(f"No fue posible conectar con el servicio de datos: {e}")
      st.stop()
    if user:
      st.session_state["user"]=user
      st.rerun()
    st.error("Credenciales inválidas o usuario no habilitado.")
  st.stop()


def render_sidebar(user):
  st.sidebar.markdown(f"<div class='sidebar-brand'><div class='brand-logo-wrap'>{brand_logo_html(54, 'brand-image')}</div><div class='sidebar-title'>LicencIA</div><div class='sidebar-sub'>Control inteligente de licencias</div></div>",unsafe_allow_html=True)
  st.sidebar.markdown(f"<span class='user-chip'>● {user.get('display_name',user['email'])}</span>",unsafe_allow_html=True)
  st.sidebar.caption(ROLE_LABELS.get(user.get("role"),user.get("role")))


def render_header(user):
  c1,c2=st.columns([5,1.1])
  with c1:
    st.markdown(f"""
    <div class='premium-hero'>
      <div class='premium-title'>LicencIA</div>
      <div class='premium-sub'>Interpreta solicitudes en lenguaje natural, valida reglas de negocio y registra cada operación con trazabilidad.</div>
      <div class='status-row'>
        <span class='status-pill'>NLP + reglas determinísticas</span>
        <span class='status-pill'>{ROLE_LABELS.get(user.get('role'),user.get('role'))}</span>
      </div>
    </div>""",unsafe_allow_html=True)
  with c2:
    st.markdown("<div style='height:1.1rem'></div>",unsafe_allow_html=True)
    if st.button("Cerrar sesión",use_container_width=True):
      logout()


def snapshot_metrics():
  licenses=list_licenses(active_only=True)
  total=sum(int(x.get("total_stock",0)) for x in licenses)
  assigned=sum(int(x.get("assigned_count",0)) for x in licenses)
  available=max(total-assigned,0)
  usage=(assigned/total*100) if total else 0
  c1,c2,c3,c4=st.columns(4)
  with c1:kpi_card("Catálogo activo",str(len(licenses)),"Licencias habilitadas")
  with c2:kpi_card("Stock total",f"{total:,}","Capacidad registrada")
  with c3:kpi_card("Asignadas",f"{assigned:,}",f"Uso global {usage:.1f}%")
  with c4:kpi_card("Disponibles",f"{available:,}","Capacidad remanente")


def render_chatbot(user):
  section_intro("Asistente de licenciamiento","Conversa de forma natural con LicencIA. Puede resolver consultas, pedir datos faltantes y ejecutar cambios únicamente después de validar y confirmar.")
  snapshot_metrics()

  if "chat_history" not in st.session_state:
    st.session_state.chat_history=[]
  if "queued_prompt" not in st.session_state:
    st.session_state.queued_prompt=None

  pending=st.session_state.get("pending_dialogue")
  if pending:
    st.markdown(f"<div class='pending-banner'><b>Solicitud en curso</b> · {pending_label(pending)}<br><span class='small-muted'>Puedes responder el dato faltante, escribir <b>cancelar</b> o hacer una consulta rápida sin perder el contexto.</span></div>",unsafe_allow_html=True)

  help_col,clear_col=st.columns([5,1])
  with help_col:
    st.markdown("""
    <div class='quick-help'><b>Prueba con lenguaje natural</b><br>
    “¿Qué usuarios tienen F3?” &nbsp;·&nbsp; “¿Cuántas E3 quedan?” &nbsp;·&nbsp; “Necesito darle Power BI a usuario@empresas.com.pe” &nbsp;·&nbsp; “Pasa Visio P2 de A a B”
    </div>""",unsafe_allow_html=True)
  with clear_col:
    if st.button("Limpiar chat",use_container_width=True):
      st.session_state.chat_history=[]
      st.session_state.pop("pending_dialogue",None)
      st.session_state.pop("pending_action",None)
      st.rerun()

  quicks=["¿Qué puedes hacer?","¿Cuántas E3 quedan?","¿Qué usuarios tienen F3?","Quiero asignar una licencia"]
  cols=st.columns(4)
  for i,q in enumerate(quicks):
    if cols[i].button(q,key=f"quick_{i}",use_container_width=True):
      st.session_state.queued_prompt=q
      st.rerun()

  for role,content in st.session_state.chat_history:
    with st.chat_message(role):
      st.write(content)

  def assistant_reply(text):
    with st.chat_message("assistant"):
      st.write(text)
    st.session_state.chat_history.append(("assistant",text))

  def resume_hint():
    p=st.session_state.get("pending_dialogue")
    if p:
      assistant_reply(f"Tu solicitud sigue pendiente: **{pending_label(p)}**. Puedes continuar respondiendo el dato que falta o escribir **cancelar**.")

  def complete_or_ask(p):
    q=next_question(p)
    if q:
      st.session_state["pending_dialogue"]=p
      assistant_reply(q)
      return False
    st.session_state.pop("pending_dialogue",None)
    if p["intent"]=="user_licenses":
      try:
        validate_corporate_user(p["target"])
        rows=user_assignments(p["target"])
        if rows:
          assistant_reply("Encontré estas licencias: **"+"**, **".join(sorted(x["license_name"] for x in rows))+"**.")
        else:
          assistant_reply("El usuario existe, pero actualmente no tiene licencias registradas.")
      except LicencIAError as e:
        assistant_reply(str(e))
      return True
    st.session_state["pending_action"]=p
    assistant_reply(f"Tengo todo listo: **{summary(p)}**. Revisa el detalle y confirma la operación.")
    return True

  pending_action=st.session_state.get("pending_action")
  if pending_action:
    st.markdown(f"<div class='pending-banner'><b>Confirmación requerida</b> · {summary(pending_action)}</div>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    if c1.button("Confirmar operación",type="primary",use_container_width=True):
      try:
        if pending_action["intent"]=="assign":
          msg=assign_license(user,pending_action["target"],pending_action["license_id"])
        elif pending_action["intent"]=="unassign":
          msg=unassign_license(user,pending_action["target"],pending_action["license_id"])
        else:
          msg=reassign_license(user,pending_action["source"],pending_action["dest"],pending_action["license_id"])
        st.success(msg)
        st.session_state.chat_history.append(("assistant",msg))
      except LicencIAError as e:
        st.error(str(e));st.session_state.chat_history.append(("assistant",str(e)))
      finally:
        st.session_state.pop("pending_action",None);st.rerun()
    if c2.button("Cancelar",use_container_width=True):
      st.session_state.pop("pending_action",None);st.info("Operación cancelada.");st.rerun()

  prompt=st.chat_input("Escribe tu solicitud en lenguaje natural…")
  queued=st.session_state.pop("queued_prompt",None)
  final_prompt=queued or prompt
  if not final_prompt:
    return

  st.session_state.chat_history.append(("user",final_prompt))
  with st.chat_message("user"):
    st.write(final_prompt)

  low=final_prompt.strip().lower()
  if low in {"cancelar","cancela","olvídalo","olvidalo","ya no","no importa"}:
    st.session_state.pop("pending_dialogue",None);st.session_state.pop("pending_action",None)
    assistant_reply("Solicitud cancelada. ¿Qué deseas hacer ahora?")
    return

  result=parse_message(final_prompt)
  record_prediction(user["email"],final_prompt,result.intent,result.confidence)

  pending=st.session_state.get("pending_dialogue")
  explicit=result.intent in {"assign","unassign","reassign","user_licenses"}
  interrupt={"greeting","wellbeing","thanks","farewell","capabilities","catalog","audit","inventory","license_holders","out_of_scope","ambiguous"}

  if pending and result.intent in interrupt:
    pass
  elif pending and explicit and result.intent!=pending.get("intent"):
    p=start_pending(result);st.session_state["pending_dialogue"]=p;complete_or_ask(p);return
  elif pending:
    p=merge_pending(pending,result);st.session_state["pending_dialogue"]=p;complete_or_ask(p);return
  elif explicit:
    complete_or_ask(start_pending(result));return

  if result.intent=="greeting":
    assistant_reply("¡Hola! 👋 Soy **LicencIA**. Puedo ayudarte con inventario, usuarios, asignaciones, desasignaciones y reasignaciones.")
    resume_hint()
  elif result.intent=="wellbeing":
    assistant_reply("Todo bien, gracias. Estoy lista para ayudarte con la gestión de licencias. ¿Qué necesitas revisar?")
    resume_hint()
  elif result.intent=="thanks":
    assistant_reply("Con gusto. Si necesitas otra gestión, dime la licencia, el usuario o la operación que quieres realizar.")
  elif result.intent=="farewell":
    assistant_reply("Hasta luego. Tu historial operativo queda registrado.")
  elif result.intent=="capabilities":
    assistant_reply("Puedo **consultar stock**, **listar usuarios por licencia**, **revisar licencias de un usuario**, **asignar**, **desasignar** y **reasignar**. También puedo orientarte sobre catálogo y auditoría según tus permisos.")
    resume_hint()
  elif result.intent=="catalog":
    rows=list_licenses(active_only=True)
    assistant_reply("Tengo configuradas **"+"**, **".join(x["name"] for x in rows)+"**.")
    resume_hint()
  elif result.intent=="ambiguous":
    if result.license_name:
      assistant_reply(f"Detecté la licencia **{result.license_name}**, pero no quiero asumir la operación. ¿Quieres ver su **stock**, ver **qué usuarios la tienen**, **asignarla**, **desasignarla** o **reasignarla**?")
    elif result.emails:
      assistant_reply(f"Detecté el usuario **{result.emails[0]}**. ¿Quieres consultar sus licencias o realizar una asignación, desasignación o reasignación?")
    else:
      assistant_reply("No tengo suficiente contexto para ejecutar una gestión con seguridad. Puedes pedirme, por ejemplo: **“¿cuántas E3 quedan?”**, **“¿qué usuarios tienen F3?”** o **“asigna Power BI a usuario@empresas.com.pe”**.")
    resume_hint()
  elif result.intent=="out_of_scope":
    assistant_reply("Ese tema está fuera de mi alcance. Estoy especializada en **gestión de licencias tecnológicas** y no respondo conocimiento general ni realizo búsquedas externas.")
    resume_hint()
  elif result.intent=="inventory":
    rows=list_licenses(active_only=True)
    if result.license_id:
      rows=[x for x in rows if x["id"]==result.license_id]
    if not rows:
      assistant_reply("No encontré una licencia activa asociada a esa consulta.")
    elif len(rows)==1:
      lic=rows[0];disp=available_stock(lic);total=int(lic.get("total_stock",0));assigned=int(lic.get("assigned_count",0));pct=(assigned/total*100) if total else 0
      assistant_reply(f"**{lic['name']}**: **{disp} disponibles**, **{assigned} asignadas**, stock total **{total}** y uso de **{pct:.1f}%**.")
    else:
      assistant_reply("Te muestro el inventario activo actual.")
      with st.chat_message("assistant"):
        st.dataframe(pd.DataFrame([{"Licencia":x["name"],"Stock total":x["total_stock"],"Asignadas":x["assigned_count"],"Disponibles":available_stock(x)} for x in rows]),use_container_width=True,hide_index=True,height=330)
      st.session_state.chat_history.append(("assistant","Inventario consultado correctamente."))
    resume_hint()
  elif result.intent=="license_holders":
    if not result.license_id:
      assistant_reply("Claro. ¿De qué licencia deseas ver los usuarios? Por ejemplo: **F3**, **Power Automate** o **Visio P2**.")
    else:
      holders=license_assignments(result.license_id,limit=2500)
      name=result.license_name or result.license_id
      users=sorted({x.get("user_email","") for x in holders if x.get("user_email")})
      assistant_reply(f"Encontré **{len(users)} usuarios** con **{name}**. Te muestro los primeros {min(30,len(users))}.")
      if users:
        with st.chat_message("assistant"):
          st.dataframe(pd.DataFrame({"Usuario":users[:30]}),use_container_width=True,hide_index=True,height=310)
          st.download_button("Descargar listado completo",data=pd.DataFrame({"Usuario":users}).to_csv(index=False).encode("utf-8-sig"),file_name=f"usuarios_{result.license_id}.csv",mime="text/csv",key=f"dl_{result.license_id}_{len(st.session_state.chat_history)}")
        st.session_state.chat_history.append(("assistant",f"Listado de usuarios con {name}."))
    resume_hint()
  elif result.intent=="audit":
    if user.get("role") not in AUDIT_ROLES:
      assistant_reply("Tu rol no tiene permisos para consultar el módulo de auditoría.")
    else:
      assistant_reply("Tienes acceso al módulo **Auditoría**, donde puedes revisar y descargar la trazabilidad de las operaciones.")
    resume_hint()


def render_inventory():
  section_intro("Inventario","Consulta stock, consumo y usuarios asociados a cada licencia.")
  rows=list_licenses();df=pd.DataFrame([{"ID":x["id"],"Licencia":x["name"],"SKU":x.get("sku"),"Grupo":x.get("group_name"),"Stock total":x.get("total_stock",0),"Asignadas":x.get("assigned_count",0),"Disponibles":available_stock(x),"% uso":round((x.get("assigned_count",0)/max(x.get("total_stock",1),1))*100,1),"Activa":x.get("active",True)} for x in rows])
  c1,c2,c3,c4=st.columns(4)
  with c1:kpi_card("Licencias activas",str(int(df["Activa"].sum()) if not df.empty else 0),"Catálogo vigente")
  with c2:kpi_card("Stock total",f"{int(df['Stock total'].sum()) if not df.empty else 0:,}","Capacidad registrada")
  with c3:kpi_card("Asignadas",f"{int(df['Asignadas'].sum()) if not df.empty else 0:,}","Uso actual")
  with c4:kpi_card("Disponibles",f"{int(df['Disponibles'].sum()) if not df.empty else 0:,}","Capacidad libre")

  st.markdown("<div style='height:.55rem'></div>",unsafe_allow_html=True)
  f1,f2=st.columns([2,1]);search=f1.text_input("Buscar licencia, SKU o grupo",placeholder="Power BI, E3, GRP_LICENCIAMS_NOMBRELICENCIA_USERS");state=f2.selectbox("Estado",["Todas","Solo activas","Solo inactivas"])
  view=df.copy()
  if search:
    mask=view.astype(str).apply(lambda c:c.str.contains(search,case=False,na=False)).any(axis=1);view=view[mask]
  if state=="Solo activas":view=view[view["Activa"]==True]
  elif state=="Solo inactivas":view=view[view["Activa"]==False]
  st.dataframe(view,use_container_width=True,hide_index=True,height=390)
  st.download_button("Descargar inventario",data=view.to_csv(index=False).encode("utf-8-sig"),file_name="licencia_inventario.csv",mime="text/csv")

  st.markdown("<div style='height:1rem'></div>",unsafe_allow_html=True)
  section_intro("Usuarios por licencia","Selecciona una licencia para revisar exactamente qué usuarios la tienen asignada y descargar el listado completo.")
  active=[x for x in rows if x.get("active",True)]
  by_name={x["name"]:x for x in active}
  lic_name=st.selectbox("Licencia a consultar",list(by_name.keys()),key="inventory_holder_license")
  lic=by_name[lic_name]
  holders=license_assignments(lic["id"],limit=5000)
  emails=sorted({x.get("user_email","") for x in holders if x.get("user_email")})
  h1,h2,h3=st.columns(3)
  with h1:kpi_card("Usuarios asignados",f"{len(emails):,}",lic_name)
  with h2:kpi_card("Disponibles",f"{available_stock(lic):,}","Stock libre")
  with h3:kpi_card("Uso",f"{(len(emails)/max(int(lic.get('total_stock',1)),1))*100:.1f}%","Sobre stock total")
  holder_search=st.text_input("Buscar usuario dentro de esta licencia",placeholder="nombre.apellido@empresas.com.pe",key="holder_search")
  filtered=[e for e in emails if not holder_search or holder_search.lower() in e.lower()]
  st.dataframe(pd.DataFrame({"Usuario":filtered}),use_container_width=True,hide_index=True,height=340)
  st.download_button("Descargar usuarios de la licencia",data=pd.DataFrame({"Usuario":emails}).to_csv(index=False).encode("utf-8-sig"),file_name=f"usuarios_{lic['id']}.csv",mime="text/csv")

def render_user_lookup():
  section_intro("Consulta por usuario","Busca una identidad corporativa y revisa sus asignaciones actuales.")
  with st.form("user_lookup_form"):
    email=st.text_input("Correo corporativo",placeholder="usuario@empresas.com.pe")
    submit=st.form_submit_button("Consultar",type="primary")
  if submit:
    try:
      u=validate_corporate_user(email);rows=user_assignments(email)
      c1,c2,c3=st.columns(3)
      with c1:kpi_card("Usuario",u.get("display_name",email),u.get("department",""))
      with c2:kpi_card("Estado","Activo" if u.get("active",True) else "Inactivo",email.lower())
      with c3:kpi_card("Licencias",str(len(rows)),"Asignaciones actuales")
      if rows:st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
      else:st.info("El usuario existe, pero no tiene licencias registradas.")
    except LicencIAError as e:st.error(str(e))


def _clean_email_lines(raw: str):
  return [x.strip().lower() for x in raw.splitlines() if x.strip()]


def _validate_reassignment_batch(source_raw: str, dest_raw: str, license_id: str):
  sources=_clean_email_lines(source_raw);destinations=_clean_email_lines(dest_raw)
  errors=[]
  if not sources and not destinations:
    return sources,destinations,["Ingresa usuarios de origen y destino."]
  if len(sources)!=len(destinations):
    errors.append(f"La cantidad de usuarios origen ({len(sources)}) debe ser igual a la cantidad destino ({len(destinations)}).")
  if len(sources)>MAX_BULK_REASSIGNMENTS:
    errors.append(f"La reasignación masiva admite hasta {MAX_BULK_REASSIGNMENTS} pares por ejecución.")
  if len(set(sources))!=len(sources):errors.append("Hay usuarios repetidos en la lista de origen.")
  if len(set(destinations))!=len(destinations):errors.append("Hay usuarios repetidos en la lista de destino.")
  if set(sources)&set(destinations):errors.append("Un usuario no puede aparecer simultáneamente como origen y destino dentro del mismo lote.")
  if errors:return sources,destinations,errors

  current={x.get("user_email","").lower() for x in license_assignments(license_id,limit=5000)}
  for email in sources:
    try:validate_corporate_user(email)
    except Exception as e:errors.append(f"Origen {email}: {e}");continue
    if email not in current:errors.append(f"Origen {email}: no tiene la licencia seleccionada.")
  for email in destinations:
    try:validate_corporate_user(email)
    except Exception as e:errors.append(f"Destino {email}: {e}");continue
    if email in current:errors.append(f"Destino {email}: ya tiene la licencia seleccionada.")
  return sources,destinations,errors


def render_bulk(user):
  section_intro("Operaciones masivas",f"Procesa cientos de registros con validación previa. Asignación/desasignación: hasta {MAX_BULK_OPERATIONS}. Reasignación: hasta {MAX_BULK_REASSIGNMENTS} pares.")
  licenses=list_licenses(active_only=True);by_name={x["name"]:x["id"] for x in licenses}
  c1,c2=st.columns(2);action=c1.selectbox("Operación",["Asignar","Desasignar","Reasignar"]);license_name=c2.selectbox("Licencia",list(by_name.keys()))
  license_id=by_name[license_name]

  if action in {"Asignar","Desasignar"}:
    raw=st.text_area("Usuarios (uno por línea)",height=270,placeholder="usuario1@empresas.com.pe\nusuario2@empresas.com.pe\nusuario3@empresas.com.pe")
    lines=_clean_email_lines(raw)
    c1,c2=st.columns(2)
    with c1:kpi_card("Registros cargados",str(len(lines)),f"Máximo {MAX_BULK_OPERATIONS}")
    with c2:kpi_card("Operación",action,license_name)
    if st.button("Ejecutar lote",type="primary",disabled=(not lines or len(lines)>MAX_BULK_OPERATIONS)):
      results=[];progress=st.progress(0)
      for idx,line in enumerate(lines,start=1):
        try:
          msg=assign_license(user,line,license_id) if action=="Asignar" else unassign_license(user,line,license_id)
          results.append({"Usuario":line,"Estado":"OK","Detalle":msg})
        except Exception as e:results.append({"Usuario":line,"Estado":"ERROR","Detalle":str(e)})
        progress.progress(idx/max(len(lines),1))
      st.dataframe(pd.DataFrame(results),use_container_width=True,hide_index=True,height=430)
    return

  st.markdown("<div class='pending-banner'><b>Reasignación masiva segura</b> · Primero carga todos los usuarios a retirar y después todos los usuarios que recibirán la licencia. LicencIA valida cardinalidad, duplicados, existencia y asignaciones antes de permitir la ejecución.</div>",unsafe_allow_html=True)
  left,right=st.columns(2)
  source_raw=left.text_area("1 · Usuarios origen — quitar licencia",height=300,placeholder="origen1@empresas.com.pe\norigen2@empresas.com.pe\norigen3@empresas.com.pe",key="bulk_sources")
  dest_raw=right.text_area("2 · Usuarios destino — agregar licencia",height=300,placeholder="destino1@empresas.com.pe\ndestino2@empresas.com.pe\ndestino3@empresas.com.pe",key="bulk_destinations")
  sources=_clean_email_lines(source_raw);destinations=_clean_email_lines(dest_raw)
  c1,c2,c3=st.columns(3)
  with c1:kpi_card("Orígenes",str(len(sources)),"Licencias a retirar")
  with c2:kpi_card("Destinos",str(len(destinations)),"Licencias a entregar")
  with c3:kpi_card("Balance",str(len(destinations)-len(sources)),"Debe ser 0")

  if st.button("Validar lote",use_container_width=False):
    src,dst,errors=_validate_reassignment_batch(source_raw,dest_raw,license_id)
    st.session_state["bulk_reassign_validation"]={"license_id":license_id,"license_name":license_name,"sources":src,"destinations":dst,"errors":errors}

  validation=st.session_state.get("bulk_reassign_validation")
  if validation and validation.get("license_id")==license_id and validation.get("sources")==sources and validation.get("destinations")==destinations:
    errors=validation.get("errors",[])
    if errors:
      st.error("No se puede ejecutar todavía. Corrige estas observaciones:")
      for err in errors:st.write(f"• {err}")
    else:
      st.success(f"Validación correcta: {len(sources)} reasignaciones listas. El total asignado no aumentará.")
      preview=pd.DataFrame({"Origen":sources,"Destino":destinations})
      st.dataframe(preview.head(30),use_container_width=True,hide_index=True,height=300)
      if len(preview)>30:st.caption(f"Vista previa de 30 de {len(preview)} pares.")
      if st.button("Ejecutar reasignación",type="primary"):
        try:
          with st.spinner("Aplicando retiros y altas en una sola transacción..."):
            outcome=bulk_reassign_license(user,sources,destinations,license_id)
          st.success(outcome["message"])
          results=pd.DataFrame({"Origen":sources,"Destino":destinations,"Estado":["OK"]*len(sources)})
          st.dataframe(results,use_container_width=True,hide_index=True,height=420)
        except Exception as e:
          st.error(str(e))
        st.session_state.pop("bulk_reassign_validation",None)

def render_audit():
  section_intro("Auditoría y trazabilidad","Revisa actor, acción, licencia, usuario objetivo, resultado y fecha de cada operación.")
  rows=recent_audit(500);df=pd.DataFrame(rows)
  if df.empty:st.info("Aún no existen eventos de auditoría.");return
  baseline_count=sum(1 for r in rows if r.get("source")=="validation_baseline_v2")
  if baseline_count:
    st.caption(f"Solicitudes de validación registradas en el periodo: {baseline_count}")
  search=st.text_input("Filtrar auditoría",placeholder="correo, acción, licencia o resultado")
  if search:
    mask=df.astype(str).apply(lambda c:c.str.contains(search,case=False,na=False)).any(axis=1);df=df[mask]
  hidden={"source","baseline","id","predicted_intent","validated_intent"}
  visible=[c for c in df.columns if c not in hidden]
  df_view=df[visible] if visible else df
  st.dataframe(df_view,use_container_width=True,hide_index=True,height=520)
  st.download_button("Descargar auditoría",data=df_view.to_csv(index=False).encode("utf-8-sig"),file_name="licencia_auditoria.csv",mime="text/csv")


def render_metrics(user):
  st.markdown("### Comparativa de métricas")
  computed,rows=compute_metrics()
  baseline_computed,baseline_rows=compute_baseline_metrics()

  base_count=len(baseline_rows)
  current_count=len(rows)
  new_count=max(current_count-base_count,0)

  b1,b2,b3=st.columns(3)
  b1.metric("Validaciones iniciales",base_count)
  b2.metric("Validaciones actuales",current_count)
  b3.metric("Nuevas validaciones",f"+{new_count}")

  if baseline_computed is None or computed is None:
    st.warning("No existen datos suficientes para mostrar la comparativa.")
    return

  bm,_=baseline_computed
  cm,_=computed
  metric_defs=[
    ("Accuracy","accuracy"),
    ("Precision","precision"),
    ("Recall","recall"),
    ("F1 Score","f1"),
  ]

  comparison=pd.DataFrame([
    {
      "Métrica":label,
      "Inicial":f"{bm[key]*100:.2f}%",
      "Actual":f"{cm[key]*100:.2f}%",
      "Variación":f"{(cm[key]-bm[key])*100:+.2f}%",
    }
    for label,key in metric_defs
  ])
  st.dataframe(comparison,use_container_width=True,hide_index=True)

  st.divider()
  st.markdown("#### Validar predicciones")
  events=[e for e in list_events(100) if not e.get("validated_intent")]
  if not events:
    st.info("No hay predicciones pendientes de validación.")
  for e in events[:20]:
    with st.expander(f"{e['predicted_intent']} · {e.get('confidence',0):.2f} · {e.get('message','')[:80]}"):
      actual=st.selectbox("Etiqueta real",list(INTENT_LABELS.keys()),format_func=lambda x:INTENT_LABELS[x],key=f"val_{e['id']}")
      if st.button("Guardar validación",key=f"save_{e['id']}"):
        validate_event(e["id"],actual,user["email"])
        st.success("Validación guardada.")
        st.rerun()


def render_config(user):
  section_intro("Administración","Configura la plataforma, revisa accesos y ajusta la experiencia visual.")
  tab1,tab2,tab3=st.tabs(["Apariencia","Accesos","Catálogo y seguridad"])

  with tab1:
    st.markdown("#### Apariencia")
    st.caption("La plataforma mantiene modo oscuro. Puedes cambiar el acento visual usado en tarjetas, botones y estados.")
    cfg=get_system_config()
    presets={"Cian / Azul":"cyan_blue","Azul / Violeta":"blue_violet","Verde / Azul":"green_blue"}
    current=cfg.get("ui_preset","cyan_blue")
    labels=list(presets.keys());idx=next((i for i,k in enumerate(labels) if presets[k]==current),0)
    selected=st.selectbox("Acento visual",labels,index=idx)
    density=st.selectbox("Densidad",["Cómoda","Compacta"],index=0 if cfg.get("ui_density","comfortable")=="comfortable" else 1)
    if st.button("Guardar apariencia",type="primary"):
      update_system_config({"ui_preset":presets[selected],"ui_density":"comfortable" if density=="Cómoda" else "compact"})
      st.success("Apariencia guardada. Se aplicará al recargar la interfaz.")
      st.rerun()

  with tab2:
    st.markdown("#### Perfiles de acceso")
    accounts=list_app_users(limit=20)
    if accounts:
      adf=pd.DataFrame(accounts)
      adf["Perfil"]=adf["role"].map({"license_manager":"Gestor de licencias","platform_admin":"Administrador"}).fillna(adf["role"])
      adf["Operaciones"]=adf["can_write"].map({True:"Habilitadas",False:"Bloqueadas"})
      adf["Administración"]=adf["admin_access"].map({True:"Habilitada",False:"Restringida"})
      st.dataframe(adf[["display_name","email","Perfil","active","Operaciones","Administración"]],use_container_width=True,hide_index=True)

      managers=[x for x in accounts if x.get("role")=="license_manager"]
      if managers:
        st.divider();st.markdown("#### Permisos del Gestor")
        selected_email=st.selectbox("Cuenta Gestor",[x["email"] for x in managers])
        manager=next(x for x in managers if x["email"]==selected_email)
        col1,col2,col3=st.columns(3)
        active=col1.toggle("Cuenta activa",value=bool(manager.get("active",True)),key=f"active_{selected_email}")
        can_write=col2.toggle("Puede gestionar licencias",value=bool(manager.get("can_write",True)),key=f"write_{selected_email}")
        admin_access=col3.toggle("Acceso a Administración",value=bool(manager.get("admin_access",False)),key=f"admin_{selected_email}")
        if st.button("Guardar permisos del Gestor",type="primary"):
          update_app_user_access(selected_email,active=active,can_write=can_write,admin_access=admin_access)
          st.success("Permisos actualizados. Se aplicarán en el siguiente inicio de sesión del Gestor.")
          st.rerun()
    else:
      st.info("No se encontraron cuentas de acceso.")

  with tab3:
    cfg=get_system_config()
    st.markdown("#### Persistencia y seguridad")
    c1,c2=st.columns(2)
    c1.text_input("Dominio corporativo permitido",value="empresas.com.pe",disabled=True)
    c2.text_input("Persistencia",value="Firebase / Firestore",disabled=True)

    failure=st.toggle(
      "Simular indisponibilidad de Firebase / Firestore",
      value=cfg.get("simulate_integration_failure",False),
      help="Mientras esté activo, las operaciones de licenciamiento fallan de forma controlada y quedan registradas en Auditoría.",
    )
    reassign_failure=st.toggle(
      "Simular falla al registrar el destino de una reasignación",
      value=cfg.get("simulate_reassignment_failure",False),
      help="Permite comprobar que una reasignación se revierte completamente si falla después de retirar temporalmente al origen.",
    )
    if st.button("Guardar configuración de persistencia"):
      update_system_config({
        "allowed_domains":["empresas.com.pe"],
        "integration_mode":"firestore",
        "integration_name":"Firebase / Firestore",
        "simulate_integration_failure":failure,
        "simulate_reassignment_failure":reassign_failure,
      })
      st.success("Configuración actualizada.")
      st.rerun()

    st.divider();st.markdown("#### Última operación persistida")
    last=latest_persisted_operation()
    if not last:
      st.info("Todavía no se ha registrado una operación de licenciamiento.")
    else:
      created=last.get("created_at")
      row={
        "Fecha / hora": created,
        "Acción": last.get("action"),
        "Actor": last.get("actor"),
        "Usuario": last.get("target_user"),
        "Licencia": last.get("license_id"),
        "Grupo": last.get("group_name"),
        "Resultado": last.get("result"),
      }
      st.dataframe(pd.DataFrame([row]),use_container_width=True,hide_index=True)
      st.caption("Las operaciones realizadas desde Chatbot u Operaciones masivas se conservan en Firebase/Firestore y también pueden revisarse en Auditoría.")

    st.divider();st.markdown("#### Catálogo de licencias")
    licenses=list_licenses();names={f"{x['name']} ({x['id']})":x for x in licenses};selected=st.selectbox("Seleccionar licencia",list(names.keys()));lic=names[selected]
    with st.form("license_edit"):
      name=st.text_input("Nombre",value=lic.get("name",""));sku=st.text_input("SKU",value=lic.get("sku",""));group=st.text_input("Grupo de seguridad",value=lic.get("group_name",""),disabled=True);total=st.number_input("Stock total",min_value=0,value=int(lic.get("total_stock",0)));active=st.checkbox("Activa",value=lic.get("active",True));save=st.form_submit_button("Guardar licencia")
    if save:
      if total<int(lic.get("assigned_count",0)):st.error("El stock total no puede ser menor que las asignaciones actuales.")
      else:upsert_license(lic["id"],{"name":name,"sku":sku,"total_stock":int(total),"active":active});st.success("Licencia actualizada.");st.rerun()


inject_styles()
user=require_login()
render_sidebar(user)
render_header(user)

role=user.get("role")
pages=["Chatbot","Inventario","Consulta por usuario"]
if role in WRITE_ROLES:pages.append("Operaciones masivas")
if role in AUDIT_ROLES:pages.append("Auditoría")
if role in METRICS_ROLES:pages.append("Métricas")
if role in CONFIG_ROLES or user.get("admin_access",False):pages.append("Administración")
icons={"Chatbot":"✦","Inventario":"▦","Consulta por usuario":"⌕","Operaciones masivas":"⇄","Auditoría":"◉","Métricas":"◫","Administración":"⚙"}
page=st.sidebar.radio("Módulos",pages,format_func=lambda x:f"{icons.get(x,'•')} {x}")
st.sidebar.markdown("---")

if page=="Chatbot":render_chatbot(user)
elif page=="Inventario":render_inventory()
elif page=="Consulta por usuario":render_user_lookup()
elif page=="Operaciones masivas":render_bulk(user)
elif page=="Auditoría":render_audit()
elif page=="Métricas":render_metrics(user)
elif page=="Administración":render_config(user)
