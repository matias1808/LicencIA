\
Write-Host "=== LicencIA - entrenamiento de Transformers ==="
python -m pip install --upgrade pip
pip install -r requirements-local-ml.txt

Write-Host "`n[1/2] Entrenando BETO..."
python scripts/train_beto_v3.py

Write-Host "`n[2/2] Entrenando DistilBERT español..."
python scripts/train_distilbert_es_v3.py

Write-Host "`nListo. Revisa las métricas de ambos modelos y selecciona el mejor F1."

Write-Host "`n[3/3] Comparando modelos..."
python scripts/compare_transformers_v4.py
