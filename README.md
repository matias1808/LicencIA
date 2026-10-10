# LicencIA — Streamlit Cloud

Versión optimizada para ejecución pública en Streamlit Community Cloud con Firebase/Firestore persistente.

# LicencIA — Streamlit + Firebase/Firestore

Prototipo funcional basado en los 28 casos de prueba y 14 historias de usuario suministrados.

## Qué incluye

- Login con correo corporativo y contraseña.
- Roles: Gestor, Consulta, Administrador, Auditor.
- 1,900 usuarios sintéticos `@empresas.com.pe`.
- Catálogo de licencias y grupos de seguridad autorizados.
- Stock simulado:
 - M365 E5, M365 E3 y M365 F3: 1,900 cada una.
 - licencias individuales/premium: 50 cada una.
- Consumo inicial aleatorio reproducible entre 75% y 95%.
- Chatbot especializado en licenciamiento:
 - asignar;
 - desasignar;
 - reasignar;
 - inventario;
 - consulta por usuario;
 - bloqueo de temas fuera del alcance.
- Confirmación antes de operaciones sensibles.
- Operaciones masivas de hasta 100 registros.
- Auditoría completa.
- Simulación de falla de integración.
- Métricas reales: Accuracy, Precision, Recall y F1-score.
- Barrido de métricas.
- Importación de validaciones históricas.
- Panel de configuración de stock, grupos, dominios y usuarios.
- Script opcional para fine-tuning de BETO con GPU local.

## Credenciales iniciales

**Gestor**
- `gestor.@empresas.com.pe`
- `LicencIA#Demo2026!`

**Administrador/configuración**
- `admin.config@empresas.com.pe`
- `Config#Demo2026!`

**Auditor**
- `auditor.@empresas.com.pe`
- `Audit#Demo2026!`

**Consulta**
- `consulta.@empresas.com.pe`
- `Consulta#Demo2026!`

> Cambia las contraseñas después del primer acceso. Son credenciales de demostración.

## Ejecución local

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
# Configura .streamlit/secrets.toml
python scripts/initialize_firestore.py
streamlit run app.py
```

## NLP

### Modo Cloud (incluido)

La app usa un clasificador supervisado `TF-IDF + Logistic Regression` entrenado con
frases de dominio y una capa determinística de seguridad para órdenes explícitas.
La extracción de correos y licencias se realiza de forma estructurada/fuzzy.

La capa determinística **no sustituye** el ML: sirve para impedir que una predicción
ambigua ejecute una operación sensible sin entidades ni confirmación.

### BETO local con tu GPU

Para entrenar un modelo contextual en español:

```bash
pip install -r requirements-local-ml.txt
python scripts/train_beto.py
```

El script usa `dccuchile/bert-base-spanish-wwm-cased` y guarda el modelo en
`models/beto_intent`.

Para Streamlit Community Cloud recomiendo mantener el clasificador ligero o servir
el modelo contextual desde un endpoint/model hub, porque cargar un transformer grande
consume bastante memoria y aumenta el tiempo de arranque.

## Métricas

No hay valores inventados. Accuracy, Precision, Recall y F1 se calculan únicamente
sobre interacciones que tengan:

- `predicted_intent`
- `validated_intent`

Con pocos registros, el panel muestra exactamente el estado de datos insuficientes.
Al ejecutar un **barrido**, se eliminan los eventos de métricas y el panel vuelve a ese estado.

## Firebase

Consulta `FIREBASE_SETUP.md`.

## Casos de prueba

Consulta `docs/TEST_CASE_MAPPING.md`.

## Cambiar el catálogo de licencias

El seed trae un catálogo inicial basado en el alcance actual. Cuando tengas el listado
definitivo, puedes:

1. editar `DEFAULT_LICENSES` en `licencia/seed_data.py`, o
2. modificar stock/nombre/grupo desde el módulo **Configuración** sin tocar código.


## Si quieres usar BETO también en producción

El proyecto deja el entrenamiento separado porque un BETO completo es mucho más pesado que
el clasificador ligero. El flujo recomendado es:

1. Entrenarlo localmente con tu GPU (`scripts/train_beto.py`).
2. Evaluar Accuracy, Precision, Recall y F1.
3. Publicar el modelo resultante en un repositorio privado de modelos o servirlo mediante un endpoint.
4. Sustituir `load_intent_model()` por el modelo contextual manteniendo la misma capa de reglas,
  entidades, confirmación y Firebase.

Así no cambias el resto de LicencIA y puedes comparar experimentalmente el baseline
TF-IDF + Logistic Regression contra BETO, como plantea tu investigación.


## Persistencia entre sesiones

El stock, asignaciones, usuarios y auditoría se almacenan en Firestore y permanecen
aunque cierres Streamlit o vuelvas meses después. Consulta `PERSISTENCIA_Y_AUDITORIA.md`.

**No vuelvas a ejecutar un reset del entorno productivo.** La inicialización normal
es idempotente: si la base ya existe, no sobrescribe el estado operativo.


## NLP reforzado (v2)

El proyecto ya incluye un modelo preentrenado con **16,901 ejemplos de dominio**
y un challenge separado de **2,110 ejemplos**.

Combina TF-IDF de palabras y caracteres con un clasificador logístico para soportar
variaciones de redacción, abreviaturas y errores leves.

Consulta `ENTRENAMIENTO_NLP.md`.

Para entrenar BETO en tu GPU:

```bash
pip install -r requirements-local-ml.txt
python scripts/train_beto.py
```
