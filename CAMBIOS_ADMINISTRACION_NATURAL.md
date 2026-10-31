# LicencIA - Administración integrada

Esta versión elimina el panel específico de validación QA y ubica cada control en su módulo funcional.

## Administración > Accesos
- Permite habilitar o restringir al Gestor para operaciones de licenciamiento.
- Permite habilitar o restringir el acceso del Gestor al módulo Administración.
- El Administrador conserva Administración habilitada.

## Métricas
- Muestra Validaciones base, Validaciones actuales y Nuevas validaciones.
- Mantiene Accuracy, Precision, Recall y F1 Score.
- La referencia inicial se puede desplegar sin agregar paneles de pruebas.

## Administración > Catálogo y seguridad
- Persistencia fija en Firebase / Firestore.
- Control independiente para simular indisponibilidad general de Firebase / Firestore.
- Control independiente para simular una falla al registrar el destino durante una reasignación.
- Muestra la última operación funcional persistida.

## Actualización
1. Copiar los archivos sobre el proyecto existente.
2. Conservar `.streamlit/secrets.toml`.
3. Ejecutar `python scripts/update_admin_controls.py` una sola vez.
4. Ejecutar `python -m streamlit run app.py`.
