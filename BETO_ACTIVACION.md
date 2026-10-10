# Activación de BETO en LicencIA

BETO queda configurado como **motor principal** de clasificación de intención. El clasificador ligero actual permanece como respaldo para baja confianza o fallas de carga.

## Dataset
- Entrenamiento: **27,117 ejemplos**
- Validación separada: **1,767 ejemplos**
- Clases: ambiguous, assign, audit, capabilities, catalog, farewell, greeting, inventory, license_holders, out_of_scope, reassign, thanks, unassign, user_licenses, wellbeing

## Arquitectura
1. Reglas de alta precisión y extracción de entidades.
2. BETO (`dccuchile/bert-base-spanish-wwm-cased`) como modelo principal.
3. Modelo TF-IDF actual como fallback cuando BETO está inseguro o no está disponible.
4. Validaciones determinísticas de usuario, licencia, stock, rol y confirmación antes de ejecutar.

## Ejecutar en Windows
Con el entorno virtual activo:

```powershell
powershell -ExecutionPolicy Bypass -File .\ENTRENAR_BETO_WINDOWS.ps1
```

Al finalizar debe existir `models/beto_licencia`. Reinicia la app:

```powershell
python -m streamlit run app.py
```

Para comprobar que está activo:

```powershell
python scripts\evaluate_beto_licencia.py
```

Debe mostrar `primary: BETO`.
