from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firebase_admin import firestore
from licencia.firebase import get_db


def main():
    db = get_db()

    # Mantener Firebase/Firestore como única capa de persistencia operativa.
    db.collection("system_config").document("main").set({
        "allowed_domains": ["empresas.com.pe"],
        "integration_mode": "firestore",
        "integration_name": "Firebase / Firestore",
        "simulate_integration_failure": False,
        "simulate_reassignment_failure": False,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    # Estado inicial esperado de los dos perfiles funcionales.
    db.collection("app_users").document("gestor.licencias@empresas.com.pe").set({
        "admin_access": False,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    db.collection("app_users").document("admin.licencia@empresas.com.pe").set({
        "admin_access": True,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    # Retira archivos locales de la propuesta anterior si llegaron a copiarse.
    for rel in ["licencia/qa_validation.py", "README_VALIDACION_QA_5CP.md"]:
        path = ROOT / rel
        if path.exists():
            path.unlink()
            print(f"Eliminado: {rel}")

    print("Actualización aplicada.")
    print("- Gestor: Administración restringida por defecto")
    print("- Administrador: Administración habilitada")
    print("- Firebase/Firestore: modo activo")
    print("- Simulaciones de falla: desactivadas")


if __name__ == "__main__":
    main()
