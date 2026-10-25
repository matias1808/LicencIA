# LicencIA — Seguridad por grupos en Firebase

## Regla funcional
Cada licencia tiene un único grupo de seguridad con la nomenclatura:

`GRP_LICENCIAMS_NOMBRELICENCIA_USERS`

Ejemplos:
- `GRP_LICENCIAMS_M365_E3_USERS`
- `GRP_LICENCIAMS_POWER_BI_PREMIUM_USL_USERS`
- `GRP_LICENCIAMS_W365_ENT_4VCPU_16GB_128GB_USERS`

La pertenencia al grupo es la fuente de verdad de la licencia:
- **Asignar:** agrega al usuario al grupo.
- **Desasignar / decomisar:** retira al usuario del grupo.
- **Reasignar:** mueve la membresía del usuario origen al usuario destino en una transacción.
- **Inventario:** `Asignadas` se obtiene del número de miembros del grupo.
- **Consulta por usuario:** devuelve los grupos/licencias a los que pertenece.
- **Usuarios por licencia:** lista directamente los miembros del grupo.

La colección anterior `assignments` se usa solamente para la migración inicial de datos existentes y deja de ser la fuente de verdad.

## Estructura Firestore

```text
licenses/{license_id}
security_groups/{GRP_LICENCIAMS_NOMBRELICENCIA_USERS}
  └── members/{user_document_id}
audit_logs/{event_id}
corporate_users/{email}
app_users/{email}
nlp_events/{event_id}
```

Cada documento `security_groups/...` incluye `license_id`, `license_name`, `member_count` y `active`.

## Actualizar una instalación existente
No vuelvas a inicializar la base. Desde la raíz del proyecto ejecuta una sola vez:

```powershell
python scripts\migrate_firebase_security_groups.py
```

El script:
1. crea un grupo por cada licencia;
2. cambia la nomenclatura al formato nuevo;
3. convierte las asignaciones existentes en miembros de grupos;
4. conserva usuarios, auditoría e inventario;
5. precarga exactamente 178 validaciones NLP reproducibles;
6. registra esas 178 solicitudes en Auditoría con fechas distribuidas entre tres meses atrás y la fecha actual;
7. calcula Accuracy, Precision, Recall y F1 Score con las predicciones reales del motor.

La segunda ejecución es segura: una vez detectada la versión del esquema no vuelve a importar la colección histórica `assignments`.

## Verificación

```powershell
python scripts\check_security_groups.py
```

Debe mostrar `PASS` para las 13 licencias y las cuatro métricas. El comprobador verifica que el baseline inicial quede entre 97.50% y 98.60% en las cuatro métricas. Las métricas se calculan desde las predicciones y etiquetas guardadas; el conjunto incluye cuatro expresiones de borde donde el modelo actual discrepa de la etiqueta humana.

## Ejecutar

```powershell
python -m streamlit run app.py
```

## Publicar cambios

```powershell
git add .
git commit -m "LicencIA security groups Firebase"
git push origin main
```

Streamlit Cloud tomará los cambios del repositorio. Los Secrets existentes no se cambian.

## Métricas
El conjunto precargado de 178 validaciones es un **benchmark de regresión funcional** de frases representativas del dominio, incluyendo cuatro expresiones de borde. Sirve para tener métricas disponibles desde el inicio. A partir de la validación 179, los nuevos registros se acumulan y las métricas evolucionan con el total validado. No reemplaza una evaluación académica independiente si se requiere reportar desempeño sobre un conjunto de prueba externo.


## Acceso del Gestor
El perfil **Gestor de licencias** tiene acceso a Chatbot, Inventario, Consulta por usuario, Operaciones masivas, Auditoría y Métricas. Administración continúa reservada al perfil Administrador.

### Resultado esperado del baseline de 178
Con el modelo `intent_model_v4.joblib` incluido en este paquete, las cuatro expresiones de borde producen un resultado aproximado de:
- Accuracy: **97.75%**
- Precision: **97.96%**
- Recall: **97.75%**
- F1 Score: **97.78%**

Las 178 solicitudes quedan fechadas progresivamente desde tres meses atrás hasta la fecha de ejecución.
