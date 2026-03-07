import time
import json
import base64

import requests

from app.core.auth_totp import get_code


def decode_jwt_payload(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        rem = len(payload) % 4
        if rem:
            payload += "=" * (4 - rem)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None


def is_valid_jwt(token):
    payload = decode_jwt_payload(token)
    if payload is None:
        return False
    exp = payload.get("exp")
    if exp is not None and exp < time.time():
        return False
    return True


def _riot_api_headers(csrf_token):
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "csrf-token": csrf_token,
        "origin": "https://account.riotgames.com",
        "referer": "https://account.riotgames.com/",
    }


def fetch_riot_id(cookies, csrf_token):
    resp = requests.get(
        "https://account.riotgames.com/api/account/v1/user",
        cookies=cookies,
        headers=_riot_api_headers(csrf_token),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    alias = data.get("alias", {})
    gn = alias.get("game_name") if alias else None
    tl = alias.get("tag_line") if alias else None
    if gn and tl:
        return f"{gn}#{tl}"
    if gn:
        return gn
    return data.get("username", data.get("sub", "Unknown"))


def enable_mfa(cookies, csrf_token):
    resp = requests.post(
        "https://account.riotgames.com/api/mfa/v2/factors/riotmobile/enable",
        cookies=cookies,
        headers=_riot_api_headers(csrf_token),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["secret"]


def verify_mfa(id_token, seed):
    resp = requests.post(
        "https://api.account.riotgames.com/mfa/v1/factor/riotmobile/verify",
        headers={
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"device": "Riot 2FA Manager", "otp": get_code(seed)}),
        timeout=15,
    )
    resp.raise_for_status()
    return resp
