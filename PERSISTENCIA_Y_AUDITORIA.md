# Persistencia real de LicencIA

## Qué queda guardado en Firebase/Firestore

La aplicación **no depende de Streamlit para conservar el estado operativo**.

Estas colecciones son persistentes:

- `corporate_users`: 1,900 usuarios corporativos.
- `licenses`: stock total y contador de asignaciones por licencia.
- `assignments`: relación actual entre usuario y licencia.
- `audit_logs`: historial de operaciones y accesos.
- `app_users`: cuentas y roles de acceso.
- `nlp_events`: predicciones/validaciones usadas para las métricas.
- `system_config`: dominios, simulación de integración e indicador de inicialización.

Cerrar el navegador, reiniciar Streamlit o volver meses después **no borra estos documentos**.

## Ejemplo de 25 + 25 + 25

Si una licencia empieza con:

- Stock total: 1,900
- Asignadas: 1,500
- Disponibles: 400

y haces 25 asignaciones:

- Asignadas: 1,525
- Disponibles: 375

Luego haces 25 reasignaciones:

- Asignadas: 1,525
- Disponibles: 375
- Cambian los propietarios, no la cantidad total.

Luego haces 25 desasignaciones:

- Asignadas: 1,500
- Disponibles: 400

El resultado exacto depende de qué licencias uses, pero cada cambio queda almacenado.

## Auditoría

Cada operación genera un registro persistente con:

- acción;
- actor;
- usuario objetivo;
- licencia;
- resultado;
- detalle;
- identificador de operación cuando corresponde;
- timestamp del servidor.

Una reasignación se registra como **una operación REASSIGN**, incluyendo origen y destino.

## Lo único temporal

`st.session_state` se usa solo para elementos de interfaz:

- sesión de navegación;
- historial visual del chat de esa sesión;
- operación pendiente de confirmación.

El inventario, las asignaciones y la auditoría **nunca dependen de `st.session_state`**.

## Inicialización segura

Ejecuta una sola vez:

```bash
python scripts/initialize_firestore.py
```

Si detecta que Firebase ya fue inicializado, **no modifica ningún dato**.

El antiguo `--reset` está bloqueado en `seed_firestore.py`.

Existe un reset destructivo solo para desarrollo y requiere dos acciones explícitas:

```bash
# Windows PowerShell
$env:LICENCIA_DESTRUCTIVE_RESET="BORRAR_TODA_LA_BASE"
python scripts/initialize_firestore.py --force-reset
```

**No ejecutes ese comando en tu entorno real.**

## Recomendación de producción

Usa dos proyectos Firebase distintos:

- `licencia-dev`: pruebas/desarrollo.
- `licencia-prod`: demostración final y datos persistentes.

Así puedes experimentar sin tocar el histórico que presentarás en la sustentación.
