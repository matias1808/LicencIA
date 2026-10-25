from __future__ import annotations

import os
import time
import tomllib
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphIntegrationError(RuntimeError):
    pass


def _from_streamlit_secrets() -> dict:
    try:
        if "azure" in st.secrets:
            return dict(st.secrets["azure"])
    except Exception:
        pass
    return {}


def _from_local_toml() -> dict:
    root = Path(__file__).resolve().parents[1]
    path = root / ".streamlit" / "secrets.toml"
    if not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        return dict(data.get("azure", {}))
    except Exception:
        return {}


def graph_settings() -> dict:
    data = {}
    data.update(_from_local_toml())
    data.update(_from_streamlit_secrets())

    # También permite variables de entorno para ejecución local/CI.
    env_map = {
        "tenant_id": "AZURE_TENANT_ID",
        "client_id": "AZURE_CLIENT_ID",
        "client_secret": "AZURE_CLIENT_SECRET",
    }
    for key, env_name in env_map.items():
        if os.getenv(env_name):
            data[key] = os.getenv(env_name)
    return data


def graph_configured() -> bool:
    cfg = graph_settings()
    return all(str(cfg.get(k, "")).strip() for k in ("tenant_id", "client_id", "client_secret"))


class MicrosoftGraphClient:
    """Cliente mínimo para Microsoft Graph usado por LicencIA.

    Requiere una aplicación de Entra ID con permisos de aplicación aprobados para
    lectura de usuarios/SKUs y modificación de membresías de grupos.
    """

    def __init__(self):
        cfg = graph_settings()
        self.tenant_id = str(cfg.get("tenant_id", "")).strip()
        self.client_id = str(cfg.get("client_id", "")).strip()
        self.client_secret = str(cfg.get("client_secret", "")).strip()
        if not all((self.tenant_id, self.client_id, self.client_secret)):
            raise GraphIntegrationError(
                "Microsoft Graph no está configurado. Define [azure] tenant_id, client_id y client_secret en Secrets."
            )
        self._token_value: str | None = None
        self._token_expires_at = 0.0
        self.session = requests.Session()

    def _token(self) -> str:
        if self._token_value and time.time() < self._token_expires_at - 120:
            return self._token_value
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        try:
            r = self.session.post(
                url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
                timeout=25,
            )
        except requests.RequestException as e:
            raise GraphIntegrationError(f"No fue posible autenticar contra Microsoft Entra ID: {e}") from e
        if not r.ok:
            raise GraphIntegrationError(
                f"Microsoft Entra ID rechazó la autenticación ({r.status_code}). Revisa tenant, app y permisos."
            )
        payload = r.json()
        self._token_value = payload.get("access_token")
        self._token_expires_at = time.time() + int(payload.get("expires_in", 3600))
        if not self._token_value:
            raise GraphIntegrationError("Entra ID no devolvió un access_token válido.")
        return self._token_value

    def _request(self, method: str, path_or_url: str, *, params=None, json=None, expected=(200, 201, 204), retry=True):
        url = path_or_url if path_or_url.startswith("https://") else GRAPH_BASE + path_or_url
        headers = {"Authorization": f"Bearer {self._token()}", "Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            r = self.session.request(method, url, headers=headers, params=params, json=json, timeout=30)
        except requests.RequestException as e:
            raise GraphIntegrationError(f"Error de comunicación con Microsoft Graph: {e}") from e
        if r.status_code == 401 and retry:
            self._token_value = None
            return self._request(method, path_or_url, params=params, json=json, expected=expected, retry=False)
        if r.status_code not in expected:
            detail = ""
            try:
                body = r.json()
                detail = (body.get("error") or {}).get("message", "")
            except Exception:
                detail = r.text[:400]
            raise GraphIntegrationError(
                f"Microsoft Graph devolvió {r.status_code}: {detail or 'respuesta no esperada'}"
            )
        if r.status_code == 204 or not r.content:
            return None
        try:
            return r.json()
        except Exception:
            return None

    def health(self) -> dict:
        data = self._request("GET", "/organization", params={"$select": "id,displayName"}) or {}
        values = data.get("value", [])
        org = values[0] if values else {}
        # subscribedSkus prueba también el acceso de lectura a Microsoft 365.
        skus = self.list_subscribed_skus()
        return {
            "ok": True,
            "organization_id": org.get("id"),
            "organization": org.get("displayName"),
            "subscribed_skus": len(skus),
        }

    def get_user(self, email: str) -> dict:
        key = quote((email or "").strip(), safe="@._-")
        try:
            data = self._request(
                "GET",
                f"/users/{key}",
                params={"$select": "id,displayName,userPrincipalName,mail,accountEnabled"},
                expected=(200, 404),
            )
        except GraphIntegrationError:
            raise
        # _request no puede diferenciar 404 porque expected incluye 404 y puede devolver JSON error.
        if not data or "error" in data or not data.get("id"):
            raise GraphIntegrationError(f"El usuario {email} no existe en Microsoft Entra ID.")
        if data.get("accountEnabled") is False:
            raise GraphIntegrationError(f"El usuario {email} está deshabilitado en Microsoft Entra ID.")
        return data

    @staticmethod
    def _escape_odata(value: str) -> str:
        return value.replace("'", "''")

    def get_group(self, display_name: str) -> dict:
        name = (display_name or "").strip()
        data = self._request(
            "GET",
            "/groups",
            params={
                "$filter": f"displayName eq '{self._escape_odata(name)}'",
                "$select": "id,displayName,securityEnabled,mailEnabled",
                "$top": "2",
            },
        ) or {}
        values = data.get("value", [])
        exact = [x for x in values if x.get("displayName") == name]
        if len(exact) != 1:
            raise GraphIntegrationError(
                f"No se encontró un único grupo autorizado en Entra ID con nombre exacto: {name}."
            )
        return exact[0]

    def is_member(self, user_email: str, group_name: str) -> bool:
        user = self.get_user(user_email)
        group = self.get_group(group_name)
        data = self._request(
            "POST",
            f"/directoryObjects/{user['id']}/checkMemberGroups",
            json={"groupIds": [group["id"]]},
        ) or {}
        return group["id"] in set(data.get("value", []))

    def add_member(self, user_email: str, group_name: str) -> dict:
        user = self.get_user(user_email)
        group = self.get_group(group_name)
        if self.is_member(user_email, group_name):
            return {"changed": False, "user": user, "group": group}
        self._request(
            "POST",
            f"/groups/{group['id']}/members/$ref",
            json={"@odata.id": f"{GRAPH_BASE}/directoryObjects/{user['id']}"},
            expected=(204,),
        )
        return {"changed": True, "user": user, "group": group}

    def remove_member(self, user_email: str, group_name: str) -> dict:
        user = self.get_user(user_email)
        group = self.get_group(group_name)
        if not self.is_member(user_email, group_name):
            return {"changed": False, "user": user, "group": group}
        self._request(
            "DELETE",
            f"/groups/{group['id']}/members/{user['id']}/$ref",
            expected=(204,),
        )
        return {"changed": True, "user": user, "group": group}

    def list_group_members(self, group_name: str, limit: int = 2500) -> list[dict]:
        group = self.get_group(group_name)
        url = f"/groups/{group['id']}/members"
        params = {"$select": "id,displayName,userPrincipalName,mail", "$top": "999"}
        out: list[dict] = []
        while url and len(out) < limit:
            data = self._request("GET", url, params=params if url.startswith("/") else None) or {}
            for x in data.get("value", []):
                out.append(x)
                if len(out) >= limit:
                    break
            url = data.get("@odata.nextLink")
            params = None
        return out

    def memberships_for_user(self, user_email: str, licenses: list[dict]) -> set[str]:
        user = self.get_user(user_email)
        group_map = {}
        for lic in licenses:
            group = self.get_group(lic.get("group_name", ""))
            group_map[group["id"]] = lic["id"]
        ids = list(group_map)
        found: set[str] = set()
        for i in range(0, len(ids), 20):
            chunk = ids[i:i + 20]
            data = self._request(
                "POST",
                f"/directoryObjects/{user['id']}/checkMemberGroups",
                json={"groupIds": chunk},
            ) or {}
            found.update(group_map[x] for x in data.get("value", []) if x in group_map)
        return found

    def list_subscribed_skus(self) -> list[dict]:
        data = self._request(
            "GET",
            "/subscribedSkus",
            params={"$select": "skuId,skuPartNumber,consumedUnits,prepaidUnits,capabilityStatus"},
        ) or {}
        return data.get("value", [])

    def sku_inventory(self) -> dict[str, dict]:
        out = {}
        for sku in self.list_subscribed_skus():
            key = str(sku.get("skuPartNumber", "")).upper()
            prepaid = sku.get("prepaidUnits") or {}
            enabled = int(prepaid.get("enabled") or 0)
            consumed = int(sku.get("consumedUnits") or 0)
            out[key] = {
                "total_stock": enabled,
                "assigned_count": consumed,
                "available": max(enabled - consumed, 0),
                "capability_status": sku.get("capabilityStatus"),
                "sku_id": sku.get("skuId"),
            }
        return out


_CLIENT: MicrosoftGraphClient | None = None


def get_graph_client() -> MicrosoftGraphClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = MicrosoftGraphClient()
    return _CLIENT
