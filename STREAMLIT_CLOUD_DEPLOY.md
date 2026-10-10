# LicencIA — Streamlit Cloud

Esta versión está preparada únicamente para Streamlit Community Cloud.

## Arquitectura

- Streamlit Cloud: interfaz + motor NLP ligero.
- Firebase / Firestore: usuarios, licencias, asignaciones, auditoría y métricas.
- `models/intent_model_v4.joblib`: modelo NLP cargado una sola vez con `st.cache_resource`.
- Catálogo de licencias: cacheado temporalmente para reducir lecturas de Firestore.

No se incluyen PyTorch, Transformers ni BETO en el deployment.

## Publicación

1. Sube esta carpeta a un repositorio privado de GitHub.
2. No subas `.streamlit/secrets.toml` ni el JSON de Firebase.
3. En Streamlit Community Cloud crea una app apuntando a `app.py`.
4. En **Advanced settings > Secrets**, pega el contenido de tu `.streamlit/secrets.toml` local.
5. Despliega.

## Persistencia

Los datos no dependen del contenedor de Streamlit. Firestore conserva stock, usuarios, asignaciones y auditoría aunque la app se reinicie o hiberne.

## Modelo

Esta versión prioriza estabilidad en Cloud. No entrena modelos al iniciar y no descarga pesos pesados.
