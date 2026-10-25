# LicencIA — Corrección dominio, grupos y métricas

## Cambios incluidos
- Único dominio permitido: `@empresas.com.pe`.
- Grupos de seguridad: `GRP_LICENCIAMS_NOMBRELICENCIA_USERS`.
- Se migran los grupos antiguos con corchetes a la nueva nomenclatura.
- Las 178 solicitudes históricas usan únicamente correos `@empresas.com.pe`.
- Se elimina de la interfaz la matriz de confusión.
- Se elimina de la interfaz la importación CSV de validaciones.
- Se elimina de la interfaz el barrido de eventos.
- Se elimina el texto explicativo debajo de las cuatro métricas.
- Las nuevas validaciones manuales continúan acumulándose.

## Aplicación
1. Copiar el contenido del paquete sobre `C:\LicencIA\LicencIA`.
2. Conservar `.streamlit\secrets.toml`.
3. Ejecutar `python -m pip install -r requirements.txt`.
4. Ejecutar `python scripts\migrate_firebase_security_groups.py` una vez.
5. Ejecutar `python scripts\check_security_groups.py`.
6. Ejecutar `python -m streamlit run app.py`.
7. Validar localmente y luego hacer commit/push a GitHub.
