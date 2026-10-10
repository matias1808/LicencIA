APP_NAME = "LicencIA"
DEFAULT_ALLOWED_DOMAINS = ["empresas.com.pe"]
MAX_BULK_OPERATIONS = 500
MAX_BULK_REASSIGNMENTS = 160
MIN_VALIDATED_EVENTS_FOR_METRICS = 4

ROLE_LABELS = {
  "license_manager": "Gestor de licencias",
  "platform_admin": "Administrador",
}

WRITE_ROLES = {"license_manager", "platform_admin"}
AUDIT_ROLES = {"platform_admin"}
METRICS_ROLES = {"platform_admin"}
CONFIG_ROLES = {"platform_admin"}

INTENT_LABELS = {
  "assign": "Asignar licencia",
  "unassign": "Desasignar licencia",
  "reassign": "Reasignar licencia",
  "inventory": "Consultar inventario",
  "user_licenses": "Consultar licencias de usuario",
  "license_holders": "Consultar usuarios por licencia",
  "audit": "Consultar auditoría",
  "catalog": "Consultar catálogo",
  "capabilities": "Consultar capacidades",
  "greeting": "Saludo",
  "wellbeing": "Conversación básica",
  "thanks": "Agradecimiento",
  "farewell": "Despedida",
  "ambiguous": "Solicitud ambigua",
  "out_of_scope": "Fuera de alcance",
}

AUTHORIZED_GROUP_PATTERN = r"^GRP_LICENCIASMS\[[A-Z0-9_]+\]_USERS$"
