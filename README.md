# LicencIA

Aplicación web desarrollada con **Streamlit** para gestionar licencias tecnológicas mediante procesamiento de lenguaje natural (NLP) y reglas de negocio.

## ¿Qué hace?

- **Asistente:** interpreta solicitudes para asignar, retirar y reasignar licencias, con validación y confirmación previa.
- **Inventario:** consulta licencias, stock, disponibilidad y usuarios asignados.
- **Consulta por usuario:** muestra las licencias de una cuenta corporativa.
- **Operaciones masivas:** procesa asignaciones, retiros y reasignaciones por lotes.
- **Auditoría:** registra las operaciones y permite consultar su trazabilidad.
- **Métricas:** muestra las validaciones y resultados de clasificación del asistente.
- **Administración:** gestiona accesos, permisos y configuración.

Los datos se almacenan en **Firebase/Firestore**. El modelo NLP vigente se encuentra en `models/intent_model_v4.joblib`.

## Ejecución

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se necesitan credenciales de Firebase en los **Secrets de Streamlit** (ejemplo: `.streamlit/secrets.toml.example`). Para inicializar una base vacía se utiliza `scripts/initialize_firestore.py` con las variables de entorno `LICENCIA_BOOTSTRAP_GESTOR_PASSWORD` y `LICENCIA_BOOTSTRAP_ADMIN_PASSWORD` configuradas.

El conjunto de **224 solicitudes sintéticas etiquetadas** utilizado para demostración está en `dataset_LicencIA/validation_224_synthetic.csv`.
