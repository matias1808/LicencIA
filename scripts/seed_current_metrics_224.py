from licencia.metric_seed import seed_current_comparison_validations

result = seed_current_comparison_validations()
print("\nCOMPARATIVA ACTUALIZADA")
print(f"Validaciones iniciales: {result['baseline_count']}")
print(f"Validaciones actuales:  {result['current_count']}")
print(f"Nuevas validaciones:    {result['new_count']}")
print()
labels = {
    'accuracy': 'Accuracy',
    'precision': 'Precision',
    'recall': 'Recall',
    'f1': 'F1 Score',
}
for key, label in labels.items():
    initial = result['baseline_metrics'][key] * 100
    current = result['current_metrics'][key] * 100
    delta = result['deltas_pp'][key]
    print(f"{label:10s}: {initial:6.2f}% -> {current:6.2f}%  ({delta:+.2f} p.p.)")
