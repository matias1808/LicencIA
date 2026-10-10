# Mapeo de casos de prueba → implementación

| Caso | Cobertura en la app |
|---|---|
| CP001 | Login con cuenta habilitada en `app_users`. |
| CP002 | Rechazo de identidad inexistente/deshabilitada. |
| CP003–CP005 | Validación de dominio y existencia en `corporate_users`. Adaptado a `@empresas.com.pe` por requerimiento actual. |
| CP006 | Clasificación de intención del chatbot. |
| CP007 | Solicitud de datos faltantes sin ejecutar cambios. |
| CP008 | `out_of_scope`: no navegación web desde el chatbot. |
| CP009 | Asignación válida con stock. |
| CP010 | Prevención de asignación duplicada. |
| CP011 | Bloqueo sin stock con mensaje controlado. |
| CP012 | Desasignación válida. |
| CP013 | Bloqueo de desasignación si no existe membresía. |
| CP014 | Reasignación atómica origen→destino. |
| CP015 | Valida destino antes de retirar al origen. |
| CP016 | Transacción evita estado parcial; errores quedan auditados. |
| CP017–CP018 | Inventario general y por licencia. |
| CP019–CP020 | Consulta de licencias por usuario y usuario inexistente. |
| CP021–CP022 | Regex de nomenclatura `GRP_LICENCIASMS[SKU]_USERS`. |
| CP023 | Accuracy, Precision, Recall y F1 derivados de eventos validados. |
| CP024 | Sin datos suficientes no se inventan porcentajes. |
| CP025 | Conector real del prototipo = Firebase; capa de repositorio queda preparada para sustituirse por Graph/Entra. |
| CP026 | Toggle de configuración `simulate_integration_failure`. |
| CP027 | `audit_logs` registra actor, usuario objetivo, licencia, acción, resultado y timestamp. |
| CP028 | Roles bloquean modificaciones no autorizadas y registran el intento. |

## Nota sobre Azure/Entra ID

Este entregable implementa el **entorno de simulación solicitado con Firebase**.
Las funciones `assign_license`, `unassign_license` y `reassign_license` están aisladas
en la capa `repository.py`, de modo que después se puede reemplazar la persistencia
de `assignments` por llamadas reales a Microsoft Graph sin rehacer la interfaz ni el NLP.
