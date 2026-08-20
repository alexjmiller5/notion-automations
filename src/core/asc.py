"""App Store Connect: Developer ID cert expiry."""

import base64
import time
from datetime import datetime, timezone

import httpx


def developer_id_expiry(settings, transport=None):
    if not settings.asc_key_id:
        return None
    import jwt

    now = int(time.time())
    token = jwt.encode(
        {"iss": settings.asc_issuer_id, "iat": now, "exp": now + 900, "aud": "appstoreconnect-v1"},
        base64.b64decode(settings.asc_p8_base64).decode(),
        algorithm="ES256",
        headers={"kid": settings.asc_key_id},
    )
    r = httpx.Client(transport=transport).get(
        "https://api.appstoreconnect.apple.com/v1/certificates",
        params={"filter[certificateType]": "DEVELOPER_ID_APPLICATION", "limit": 200},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    dates = [
        datetime.fromisoformat(c["attributes"]["expirationDate"]).astimezone(timezone.utc).date()
        for c in r.json()["data"]
    ]
    return max(dates) if dates else None
