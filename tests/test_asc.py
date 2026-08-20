import httpx

from core.asc import developer_id_expiry
from core.config import Settings


def make_settings(**kw):
    return Settings(notion_api_token="t", **kw)


def test_no_creds_returns_none():
    assert developer_id_expiry(make_settings()) is None


def test_max_expiry_chosen(monkeypatch):
    monkeypatch.setattr("jwt.encode", lambda *a, **kw: "tok")
    settings = make_settings(asc_key_id="k", asc_issuer_id="i", asc_p8_base64="cA==")

    def handler(req):
        assert req.headers["Authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"attributes": {"expirationDate": "2027-02-01T00:00:00.000+00:00"}},
                    {"attributes": {"expirationDate": "2026-11-15T00:00:00.000+00:00"}},
                ]
            },
        )

    from datetime import date

    expiry = developer_id_expiry(settings, transport=httpx.MockTransport(handler))
    assert expiry == date(2027, 2, 1)
