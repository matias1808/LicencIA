import json
from pathlib import Path

JSON_FILE = "licencia-prod-2-firebase-adminsdk-fbsvc-9b33c478d7.json"

with open(JSON_FILE, "r", encoding="utf-8") as f:
    d = json.load(f)

p = Path(".streamlit/secrets.toml")
p.parent.mkdir(parents=True, exist_ok=True)

keys = [
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
    "universe_domain",
]

lines = ["[firebase]"]

for key in keys:
    lines.append(f"{key} = {json.dumps(d[key])}")

lines += [
    "",
    "[app]",
    'environment = "demo"',
]

p.write_text("\n".join(lines), encoding="utf-8")

print("secrets.toml creado correctamente")