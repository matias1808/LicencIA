Write-Host "=== LicencIA | BETO ==="

Write-Host "1. Instalando PyTorch con CUDA 12.8..."
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

Write-Host "`n2. Instalando Transformers..."
python -m pip install -r requirements-beto.txt

Write-Host "`n3. Verificando GPU..."
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA disponible:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

Write-Host "`n4. Entrenando BETO para LicencIA..."
python scripts\train_beto_licencia.py

Write-Host "`n5. Evaluando motor integrado..."
python scripts\evaluate_beto_licencia.py

Write-Host "`nBETO quedó instalado en models\beto_licencia. Reinicia Streamlit."
