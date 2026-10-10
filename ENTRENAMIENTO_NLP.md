# Entrenamiento NLP de LicencIA — versión reforzada

## Modelo incluido

La aplicación incluye un modelo ya entrenado y listo para Streamlit:

- **Arquitectura:** TF-IDF de palabras (1–3 n-gramas) + TF-IDF de caracteres (3–5 n-gramas) + clasificador logístico SGD.
- **Ejemplos de entrenamiento:** 16,901
- **Ejemplos challenge separados:** 2,110
- **Intenciones:** assign, audit, greeting, inventory, out_of_scope, reassign, unassign, user_licenses
- **Accuracy interna en challenge sintético:** 86.97 %
- **Precision ponderada:** 88.53 %
- **Recall ponderado:** 86.97 %
- **F1 ponderado:** 87.03 %

> Estas métricas son una comprobación técnica interna sobre un challenge sintético construido
> con plantillas distintas a las de entrenamiento. **No son los resultados finales de la tesis.**
> Las métricas del paper deben calcularse con solicitudes reales/validadas.

## Qué se añadió

- miles de formas de pedir asignación, desasignación y reasignación;
- inventario general y por producto;
- consulta de licencias por usuario;
- auditoría;
- saludos y ayuda;
- solicitudes fuera del alcance;
- expresiones formales e informales;
- pequeñas faltas ortográficas;
- alias como `PowerBI`, `E3`, `E5`, `F3`, `W365`, `Cloud PC`, etc.;
- correos tomados del universo de 1,900 usuarios ficticios.

El TF-IDF de caracteres mejora la tolerancia ante errores como `reasignr`, `desasignr`,
variaciones de espacios o `PowerBI`.

## Reentrenar el modelo ligero

```bash
python scripts/retrain_intent_model.py
```

## Entrenar BETO localmente

```bash
pip install -r requirements-local-ml.txt
python scripts/train_beto.py
```

El script usa el dataset ampliado `data/nlp_training_v2.csv`.

## Seguridad

Aunque el modelo tenga alta confianza, LicencIA no ejecuta directamente una operación.
Mantiene:

1. extracción de usuario y licencia;
2. validación contra Firebase;
3. validación de stock y asignación existente;
4. reglas determinísticas;
5. confirmación explícita;
6. auditoría persistente.

El modelo interpreta la intención; las reglas controlan la ejecución.


## QA manual adicional

Se ejecutó una comprobación manual adicional con frases no utilizadas como plantillas
principales de entrenamiento, incluyendo reasignaciones redactadas como
“quítale X a A y dásela a B”, consultas de cupos, alias y solicitudes fuera del alcance.

Resultado del lote manual: **11/12 clasificaciones correctas**.

El detalle queda en `data/nlp_manual_qa_v2.csv`.
