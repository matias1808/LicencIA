# NLP conversacional de LicencIA v3

## Modelo incluido y ya entrenado
- Ejemplos de entrenamiento: **26,716**
- Challenge sintético separado: **1,876**
- Intenciones: ambiguous, assign, audit, capabilities, catalog, farewell, greeting, inventory, out_of_scope, reassign, thanks, unassign, user_licenses, wellbeing
- Accuracy challenge: **74.25%**
- Precision ponderada: **83.26%**
- Recall ponderado: **74.25%**
- F1 ponderado: **74.06%**

Estas métricas son QA interno sintético; no sustituyen las validaciones reales del paper.

## Comportamiento conversacional
LicencIA ahora:
- saluda y responde conversación básica;
- explica sus funciones;
- lista su catálogo;
- rechaza conocimiento general fuera del dominio;
- detecta solicitudes ambiguas y pregunta;
- conserva el contexto de una operación incompleta durante la sesión;
- pide licencia, usuario, origen o destino cuando faltan;
- nunca ejecuta hasta tener entidades, reglas y confirmación.

Ejemplo:
1. Usuario: `quiero asignar una licencia`
2. LicencIA: `¿Qué licencia deseas gestionar?`
3. Usuario: `Power BI`
4. LicencIA: `¿Cuál es el correo corporativo del usuario?`
5. Usuario: `juan.perez0001@empresas.com.pe`
6. LicencIA valida y muestra la confirmación.

Para transformers consulta `DISTILBERT_BETO.md`.


## Refuerzo v4

El modelo ligero se volvió a entrenar incorporando el challenge anterior como nueva evidencia,
más paraphrases adicionales. El nuevo conjunto de entrenamiento contiene **40,255 ejemplos**.

Se creó además un **stress test nuevo y no utilizado para entrenamiento** con **653 ejemplos**.

Modelo seleccionado: `sgd_unbalanced_a5e6`

- Accuracy stress: **75.04%**
- Precision ponderada: **79.63%**
- Recall ponderado: **75.04%**
- F1 ponderado: **74.64%**

Para entrenar los transformers en Windows puedes ejecutar:

```powershell
powershell -ExecutionPolicy Bypass -File .\ENTRENAR_TRANSFORMERS_WINDOWS.ps1
```
