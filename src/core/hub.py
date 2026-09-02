"""life-data hub client - pulls the automation catalog rows at run time.

The only module besides notion.py that does network I/O.
"""

import httpx


def pull_rows(url: str, token: str, table: str, columns) -> list[dict]:
    resp = httpx.post(
        f"{url}/v1/rows/pull",
        json={"table": table, "columns": list(columns), "since": ""},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["rows"]
