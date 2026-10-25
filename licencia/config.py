APP_NAME = "LicencIA"

# LicencIA acepta exclusivamente el dominio corporativo empresas.com.pe.
DEFAULT_ALLOWED_DOMAINS = ["empresas.com.pe"]

MAX_BULK_OPERATIONS = 500
MAX_BULK_REASSIGNMENTS = 160
MIN_VALIDATED_EVENTS_FOR_METRICS = 20

ROLE_LABELS = {
    "license_manager": "Gestor de licencias",
    "platform_admin": "Administrador",
}

WRITE_ROLES = {"license_manager", "platform_admin"}
AUDIT_ROLES = {"license_manager", "platform_admin"}
METRICS_ROLES = {"license_manager", "platform_admin"}
CONFIG_ROLES = {"platform_admin"}

INTENT_LABELS = {
    "assign": "Asignar licencia",
    "unassign": "Desasignar / decomisar licencia",
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

# Cada licencia tiene exactamente un grupo de seguridad en Firebase.
# Ejemplo: GRP_LICENCIAMS_M365_E3_USERS
AUTHORIZED_GROUP_PATTERN = r"^GRP_LICENCIAMS_[A-Z0-9_]+_USERS$"
SECURITY_GROUPS_COLLECTION = "security_groups"

SUPPORTED_INTEGRATION_MODES = {"firestore", "graph"}
DEFAULT_INTEGRATION_MODE = "firestore"
