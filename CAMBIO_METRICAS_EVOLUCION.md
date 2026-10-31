# Evolución de métricas - corrección

La pantalla Métricas ahora separa claramente:

- Validaciones iniciales: baseline congelado (178 registros).
- Validaciones actuales: todos los registros que tienen `validated_intent` en Firebase.
- Nuevas validaciones: actuales - iniciales.

La comparación muestra Accuracy, Precision, Recall y F1 Score en tres formas:

1. Valor inicial.
2. Valor actual.
3. Variación en puntos porcentuales.

Cada vez que se guarda una validación manual se limpia el cache de métricas y Streamlit recalcula inmediatamente el estado actual.

No se requiere volver a ejecutar `initialize_firestore.py` ni las migraciones de grupos.
