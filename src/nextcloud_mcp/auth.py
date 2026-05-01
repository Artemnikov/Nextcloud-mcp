import os
from dataclasses import dataclass

import httpx


@dataclass
class Config:
    base_url: str
    user: str
    auth: httpx.BasicAuth

    @property
    def dav_url(self) -> str:
        return f"{self.base_url}/remote.php/dav/files/{self.user}"


def get_config() -> Config:
    base = os.environ.get("NEXTCLOUD_URL")
    user = os.environ.get("NEXTCLOUD_USER")
    pw = os.environ.get("NEXTCLOUD_APP_PASSWORD")
    missing = [k for k, v in [
        ("NEXTCLOUD_URL", base),
        ("NEXTCLOUD_USER", user),
        ("NEXTCLOUD_APP_PASSWORD", pw),
    ] if not v]
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Create an app password in Nextcloud → Settings → Security → Devices & sessions."
        )
    return Config(base_url=base.rstrip("/"), user=user, auth=httpx.BasicAuth(user, pw))
