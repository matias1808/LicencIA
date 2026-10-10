# LicencIA — despliegue Cloud seguro con BETO local

## Arquitectura de ejecución

LicencIA utiliza **una sola base de código**, pero selecciona el motor NLP según el entorno:

- **PC local con CUDA + BETO entrenado:** BETO es el motor principal.
- **Streamlit Community Cloud / CPU:** se usa automáticamente el clasificador ligero.
- **Fallback:** incluso en local, si BETO falla o no existe, la aplicación continúa con el modelo ligero.

Esto evita cargar aproximadamente cientos de MB de pesos de BETO en Community Cloud y reduce el riesgo de superar la memoria disponible.

## Importante

El archivo `requirements.txt` de este paquete **NO instala PyTorch ni Transformers**. Esto es intencional para Community Cloud.

Para entrenar y usar BETO localmente instala por separado:

```powershell
pip install -r requirements-beto.txt
```

más PyTorch CUDA según el script de entrenamiento BETO ya preparado.

## Antes de subir a GitHub

No subas el modelo BETO pesado a Community Cloud. Añade a tu `.gitignore`:

```gitignore
models/beto_licencia/
models/beto_licencia/**
```

El modelo ligero `models/intent_model_v4.joblib` **sí debe permanecer** porque es el motor Cloud.

## Verificar el motor activo

Local con GPU:

```powershell
python scripts\check_nlp_engine.py
```

Debe mostrar algo como:

```json
{
  "primary": "BETO",
  "device": "cuda:0",
  "active": true
}
```

En Streamlit Cloud debe mostrar conceptualmente:

```json
{
  "primary": "TF-IDF + clasificador logístico",
  "device": "CPU",
  "active": false,
  "reason": "CPU detectada: modo Cloud seguro"
}
```

## Modos opcionales

La variable de entorno `LICENCIA_NLP_MODE` acepta:

- `auto` (predeterminado): BETO solo con GPU; CPU usa modelo ligero.
- `light`: fuerza siempre el modelo ligero.
- `beto`: fuerza BETO incluso en CPU. **No recomendado en Streamlit Community Cloud.**

## Publicación

1. Sube el proyecto a GitHub sin `models/beto_licencia/`.
2. Mantén el `requirements.txt` liviano de este paquete.
3. En Streamlit Community Cloud conecta el repositorio y selecciona `app.py`.
4. En **Secrets**, pega tu `.streamlit/secrets.toml` de Firebase.
5. No agregues `LICENCIA_NLP_MODE=beto` en Cloud.

Firebase sigue almacenando usuarios, stock, asignaciones y auditoría externamente. Reinicios del contenedor de Streamlit no eliminan esos datos.
