from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from licencia.metric_seed import seed_baseline_validations
from licencia.metrics import compute_baseline_metrics
from licencia.repository import get_system_config, update_system_config

cfg = get_system_config()
version = int(cfg.get("metrics_baseline_version", 0) or 0)
result = seed_baseline_validations(reset_all=version < 2)
update_system_config({"metrics_baseline_version": 2})
computed, rows = compute_baseline_metrics()
print(f"Validaciones precargadas: {result['count']}")
print(f"Solicitudes históricas en auditoría: {result['audit_count']}")
if computed:
    metrics, _ = computed
    for label, key in [("Accuracy","accuracy"),("Precision","precision"),("Recall","recall"),("F1 Score","f1")]:
        print(f"{label}: {metrics[key]*100:.2f}%")
else:
    print(f"No hay suficientes registros validados: {len(rows)}")
