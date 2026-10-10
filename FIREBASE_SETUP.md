# Configuración de Firebase / Firestore

## 1. Crear el proyecto

1. Entra a Firebase Console.
2. Crea un proyecto nuevo, por ejemplo `licencia-`.
3. Ve a **Build → Firestore Database → Create database**.
4. Selecciona una región cercana a tus usuarios.
5. Para este prototipo, el acceso a Firestore se hace **solo desde el servidor** mediante Firebase Admin SDK.

## 2. Obtener la Service Account

1. Firebase → **Project settings → Service accounts**.
2. Selecciona **Generate new private key**.
3. Descarga el JSON.
4. **Nunca lo subas a GitHub.**

## 3. Crear los secretos locales

Copia:

```text
.streamlit/secrets.toml.example
```

como:

```text
.streamlit/secrets.toml
```

y reemplaza los valores con los del JSON.

## 4. Sembrar la base

Desde la raíz:

```bash
pip install -r requirements.txt
python scripts/initialize_firestore.py
```

Esto crea:

- 1,900 usuarios corporativos `@empresas.com.pe`.
- catálogo inicial de licencias;
- 75%–95% de consumo simulado por licencia;
- cuentas de acceso por rol;
- configuración del entorno.

## 5. Streamlit Community Cloud

1. Sube este proyecto a un repositorio de GitHub.
2. En Streamlit Community Cloud crea una app con `app.py`.
3. En **Advanced settings / Secrets**, pega el contenido de tu `secrets.toml`.
4. No subas el archivo real de secretos al repositorio.

## 6. Reglas de Firestore

El archivo `firestore.rules` niega acceso directo desde clientes. La app usa Admin SDK
desde el servidor y controla permisos por rol dentro de LicencIA.


## Importante: no reinicializar producción

La inicialización normal detecta el marcador `initialized` en Firestore y no toca
los datos existentes. No borres colecciones ni uses el reset destructivo en el
proyecto Firebase que utilices para tus pruebas finales.
