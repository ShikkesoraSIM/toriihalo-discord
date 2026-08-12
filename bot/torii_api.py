from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import quote

import httpx


logger = logging.getLogger(__name__)


class ToriiApiError(Exception):
    pass


class ToriiApiUnauthorized(ToriiApiError):
    pass


class ToriiApiClient:
    def __init__(
        self,
        base_url: str,
        web_base_url: str,
        token: str | None = None,
        mod_alert_token: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
        oauth_username: str | None = None,
        oauth_password: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base_headers = {
            "User-Agent": "torii-discord-bot/0.1.0",
            "Accept": "application/json",
            "x-api-version": "20220705",
        }
        self._static_token = token
        self._mod_alert_token = mod_alert_token
        self._oauth_client_id = oauth_client_id
        self._oauth_client_secret = oauth_client_secret
        self._oauth_username = oauth_username
        self._oauth_password = oauth_password
        self._oauth_access_token: str | None = None
        self._oauth_expires_at: float = 0.0
        self._oauth_lock = asyncio.Lock()
        self._auth_unavailable_logged = False

        self.web_base_url = web_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers=self._base_headers,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _fetch_oauth_token(self) -> None:
        if not self._oauth_client_id or not self._oauth_client_secret:
            raise ToriiApiUnauthorized(
                "Missing Torii auth. Set TORII_API_TOKEN or TORII_OAUTH_CLIENT_ID/TORII_OAUTH_CLIENT_SECRET."
            )

        # Prefer password grant when credentials are supplied (required by this Torii deployment for some endpoints).
        data: dict[str, str] = {
            "client_id": self._oauth_client_id,
            "client_secret": self._oauth_client_secret,
        }
        if self._oauth_username and self._oauth_password:
            data.update(
                {
                    "grant_type": "password",
                    "username": self._oauth_username,
                    "password": self._oauth_password,
                    "scope": "*",
                }
            )
        else:
            data.update(
                {
                    "grant_type": "client_credentials",
                    "scope": "public",
                }
            )

        try:
            response = await self._client.post(
                "/oauth/token",
                data=data,
            )
        except httpx.HTTPError as exc:
            raise ToriiApiError(f"OAuth token request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ToriiApiUnauthorized(
                f"OAuth token request failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in", 3600)
        if not access_token:
            raise ToriiApiUnauthorized("OAuth token response did not include access_token.")

        self._oauth_access_token = str(access_token)
        self._oauth_expires_at = time.time() + max(60, int(expires_in) - 60)

    async def _get_auth_headers(self) -> dict[str, str]:
        if self._static_token:
            return {"Authorization": f"Bearer {self._static_token}"}

        async with self._oauth_lock:
            if not self._oauth_access_token or time.time() >= self._oauth_expires_at:
                await self._fetch_oauth_token()
            if not self._oauth_access_token:
                raise ToriiApiUnauthorized("No API token available.")
            return {"Authorization": f"Bearer {self._oauth_access_token}"}

    async def _request(self, method: str, path: str, *, skip_auth: bool = False, _retried: bool = False, **kwargs) -> dict | list:
        headers = kwargs.pop("headers", {})
        if skip_auth:
            auth_headers = {}
        else:
            try:
                auth_headers = await self._get_auth_headers()
            except ToriiApiUnauthorized as exc:
                # Most read-only v2 endpoints are public. If OAuth is not usable in this environment,
                # keep stats commands functional by falling back to unauthenticated requests.
                if method.upper() == "GET":
                    if not self._auth_unavailable_logged:
                        logger.warning("API auth unavailable, falling back to public GET requests: %s", exc)
                        self._auth_unavailable_logged = True
                    auth_headers = {}
                else:
                    raise
        merged_headers = {**headers, **auth_headers}
        try:
            response = await self._client.request(method, path, headers=merged_headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ToriiApiError(f"Request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            # self-heal: con OAuth, si el token quedo invalido ANTES de expirar
            # (server reiniciado, token revocado, etc.), lo tiramos y reintentamos UNA
            # vez con uno fresco. asi el bot nunca se queda "sin token" hasta reinicio.
            if not skip_auth and not _retried and self._oauth_client_id and not self._static_token:
                async with self._oauth_lock:
                    self._oauth_access_token = None
                    self._oauth_expires_at = 0.0
                logger.info("Torii API 401/403 with OAuth; refreshing token and retrying once.")
                return await self._request(method, path, skip_auth=skip_auth, _retried=True, headers=headers, **kwargs)
            raise ToriiApiUnauthorized("Torii API authorization failed. Check OAuth client / TORII_API_TOKEN.")
        if response.status_code >= 400:
            detail: str
            try:
                payload = response.json()
                detail = str(payload.get("detail", payload))
            except Exception:
                detail = response.text
            raise ToriiApiError(f"{method} {path} failed ({response.status_code}): {detail}")

        data = response.json()
        return data

    async def get_user(self, identifier: str | int, mode: str | None = None) -> dict:
        ident = quote(str(identifier).strip())
        if mode:
            return await self._request("GET", f"/api/v2/users/{ident}/{mode}")
        return await self._request("GET", f"/api/v2/users/{ident}")

    async def get_user_scores(
        self,
        user_id: int,
        score_type: str,
        *,
        mode: str | None = None,
        limit: int = 5,
        offset: int = 0,
        include_fails: bool = False,
    ) -> list[dict]:
        params: dict[str, str | int | bool] = {
            "limit": max(1, min(limit, 50)),
            "offset": max(0, offset),
            "include_fails": include_fails,
        }
        if mode:
            params["mode"] = mode
        data = await self._request("GET", f"/api/v2/users/{user_id}/scores/{score_type}", params=params)
        if isinstance(data, list):
            return data
        raise ToriiApiError(f"Unexpected response for user scores: {type(data)}")

    async def get_score(self, score_id: int) -> dict:
        data = await self._request("GET", f"/api/v2/scores/{score_id}")
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for score: {type(data)}")

    async def get_beatmap(self, beatmap_id: int) -> dict:
        data = await self._request("GET", f"/api/v2/beatmaps/{beatmap_id}")
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for beatmap: {type(data)}")

    async def get_beatmap_scores(
        self,
        beatmap_id: int,
        *,
        mode: str = "osu",
        leaderboard_type: str = "global",
        limit: int = 10,
    ) -> dict:
        params = {
            "mode": mode,
            "type": leaderboard_type,
            "limit": max(1, min(limit, 50)),
        }
        data = await self._request("GET", f"/api/v2/beatmaps/{beatmap_id}/scores", params=params)
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for beatmap scores: {type(data)}")

    async def get_rankings(
        self,
        *,
        mode: str = "osu",
        sort: str = "performance",
        page: int = 1,
        country: str | None = None,
    ) -> dict:
        params: dict[str, str | int] = {"page": max(1, page)}
        if country:
            params["country"] = country.upper()
        data = await self._request("GET", f"/api/v2/rankings/{mode}/{sort}", params=params)
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for rankings: {type(data)}")

    async def get_country_rankings(
        self,
        *,
        mode: str = "osu",
        sort: str = "performance",
        page: int = 1,
    ) -> dict:
        params: dict[str, str | int] = {"page": max(1, page)}
        data = await self._request("GET", f"/api/v2/rankings/{mode}/country/{sort}", params=params)
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for country rankings: {type(data)}")

    async def get_pending_mod_alerts(self, *, limit: int = 10) -> list[dict]:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "GET",
            "/api/private/mod-alerts/pending",
            params={"limit": max(1, min(limit, 50))},
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        if isinstance(data, dict):
            alerts = data.get("alerts", [])
            if isinstance(alerts, list):
                return alerts
        raise ToriiApiError(f"Unexpected response for mod alerts: {type(data)}")

    async def mark_mod_alert_dispatched(self, alert_id: int) -> None:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        await self._request(
            "POST",
            f"/api/private/mod-alerts/{alert_id}/dispatch",
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )

    async def whitelist_high_pp_user(self, alert_id: int, moderator_id: int) -> dict:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "POST",
            f"/api/private/mod-alerts/{alert_id}/whitelist-user",
            params={"moderator_id": moderator_id},
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        return data if isinstance(data, dict) else {}

    async def ban_alert_beatmapset(self, alert_id: int, reason: str | None = None) -> dict:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "POST",
            f"/api/private/mod-alerts/{alert_id}/ban-beatmapset",
            params={"reason": reason} if reason else None,
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        return data if isinstance(data, dict) else {}

    async def resolve_mod_alert(self, alert_id: int) -> None:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        await self._request(
            "POST",
            f"/api/private/mod-alerts/{alert_id}/resolve",
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )

    async def get_user_high_pp_plays(self, user_id: int, *, limit: int = 25) -> dict:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "GET",
            f"/api/private/mod-alerts/user/{user_id}/high-pp",
            params={"limit": max(1, min(limit, 100))},
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for user high pp plays: {type(data)}")

    async def get_pending_ordr_renders(self, *, limit: int = 5) -> list[dict]:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "GET",
            "/api/private/ordr-renders/pending",
            params={"limit": max(1, min(limit, 20))},
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        if isinstance(data, dict):
            renders = data.get("renders", [])
            if isinstance(renders, list):
                return renders
        raise ToriiApiError(f"Unexpected response for ordr renders: {type(data)}")

    async def get_active_ordr_renders(self, *, limit: int = 10) -> list[dict]:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "GET",
            "/api/private/ordr-renders/active",
            params={"limit": max(1, min(limit, 25))},
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        if isinstance(data, dict):
            renders = data.get("renders", [])
            if isinstance(renders, list):
                return renders
        raise ToriiApiError(f"Unexpected response for active ordr renders: {type(data)}")

    async def set_ordr_render_message(self, record_id: int, message_id: int) -> None:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        await self._request(
            "POST",
            f"/api/private/ordr-renders/{record_id}/message",
            params={"message_id": message_id},
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )

    async def mark_ordr_render_dispatched(self, record_id: int) -> None:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        await self._request(
            "POST",
            f"/api/private/ordr-renders/{record_id}/dispatch",
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )

    async def get_daily_challenge_schedule(self) -> dict:
        if not self._mod_alert_token:
            raise ToriiApiUnauthorized("Missing MOD_ALERT_TOKEN.")
        data = await self._request(
            "GET",
            "/api/private/daily-challenge/schedule",
            headers={"X-Torii-Mod-Alert-Token": self._mod_alert_token},
            skip_auth=True,
        )
        if isinstance(data, dict):
            return data
        raise ToriiApiError(f"Unexpected response for daily challenge schedule: {type(data)}")

    def score_url(self, score_id: int | str) -> str:
        return f"{self.web_base_url}/scores/{score_id}"

    def beatmap_url(self, beatmap_id: int | str) -> str:
        return f"{self.web_base_url}/beatmaps/{beatmap_id}"

    def user_url(self, user_id: int | str) -> str:
        return f"{self.web_base_url}/users/{user_id}"
