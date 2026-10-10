# BETO + DistilBERT / “DistilBETO”

Para el paper conviene distinguir:

- **BETO**: BERT entrenado específicamente con corpus en español (`dccuchile/bert-base-spanish-wwm-cased`).
- **DistilBERT español**: modelo reducido/ligero basado en DistilBERT para español (`Recognai/distilbert-base-es-multilingual-cased`).
- Un modelo público llamado “BETO destilado” que aparece en Hugging Face está ajustado a **Question Answering**,
  no a clasificación de intenciones; por eso no se usa directamente como clasificador de LicencIA.

## Entrenar BETO

```bash
pip install -r requirements-local-ml.txt
python scripts/train_beto_v3.py
```

## Entrenar DistilBERT español

```bash
python scripts/train_distilbert_es_v3.py
```

Ambos entrenan las mismas intenciones y el mismo dataset `nlp_training_v3.csv`, permitiendo comparar
Accuracy, Precision, Recall y F1 bajo el mismo problema.

## Recomendación de uso

1. Entrena ambos localmente con GPU.
2. Evalúa en un conjunto real separado.
3. Selecciona el modelo por F1 y por errores críticos, no solo por Accuracy.
4. Publica el modelo ganador en un endpoint o repositorio privado y úsalo en Streamlit.
5. Conserva la capa de reglas/confirmación aunque el transformer tenga alta confianza.

No es recomendable ejecutar un transformer grande directamente en Streamlit Community Cloud si el plan
de recursos es limitado; es mejor cargar un modelo ligero o consumir un endpoint.
