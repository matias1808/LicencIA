from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from licencia.seed_data import seed_all


if __name__ == "__main__":
    destructive = "--force-reset" in sys.argv
    if destructive:
        confirmation = os.environ.get("LICENCIA_DESTRUCTIVE_RESET", "")
        if confirmation != "BORRAR_TODA_LA_BASE":
            raise SystemExit(
                "Reset bloqueado. Si realmente quieres borrar TODO el entorno, "
                "define LICENCIA_DESTRUCTIVE_RESET=BORRAR_TODA_LA_BASE y vuelve a ejecutar."
            )

    result = seed_all(reset=destructive, allow_destructive=destructive)
    print(result)
    if result.get("status") != "already_initialized":
        print("\nCredenciales iniciales:")
        print("gestor.licencias@empresas.com.pe / LicencIA#Gestor2026!")
        print("admin.licencia@empresas.com.pe / LicencIA#Admin2026!")
