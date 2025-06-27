# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for snap tests."""

import datetime
import logging
import os
import random
import string
import subprocess
from typing import Generator, Callable

import pytest
import requests

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--snap-file", action="store", required=True)
    parser.addoption("--xargs", action="store", default="")
    parser.addoption("--installed-snap", action="store", default="")
    parser.addoption("--https-proxy", action="store", default="")

@pytest.fixture(name="run", scope="session")
def fixture_run(pytestconfig) -> Callable[[list[str], str | None], str]:
    xargs = pytestconfig.getoption("xargs")
    if not xargs:
        xargs = []
    else:
        xargs = xargs.split()

    def run(cmd: list[str], redact: str | None = None) -> str:
        command_line = " ".join(xargs + cmd)
        if redact:
            command_line = command_line.replace(redact, "***")
        logger.info(f"executing command: {command_line}")
        return subprocess.check_output(xargs + cmd, encoding="utf-8")

    return run


@pytest.fixture(scope="module", name="charmed_cloudflared_snap")
def install_charmed_cloudflared_snap(pytestconfig, run) -> Generator[str, None, None]:
    installed = pytestconfig.getoption("--installed-snap")
    if installed:
        yield installed
        return
    snap_file = pytestconfig.getoption("--snap-file")
    nonce = "".join(random.choice(string.ascii_lowercase) for _ in range(4))
    name = f"charmed-cloudflared_test{nonce}"
    run(["sudo", "snap", "install", "--dangerous", "--name", name, snap_file])

    yield name

    run(["sudo", "snap", "remove", name, "--purge"])


class CloudflareAPI:
    """Cloudflare API."""

    def __init__(self, account_id, api_token) -> None:
        """Initialize the Cloudflare API.

        Args:
            account_id: cloudflare account ID.
            api_token: cloudflare API token.
        """
        self._endpoint = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/cfd_tunnel"
        )
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        )
        self._created_tunnels: list[str] = []
        self._tunnel_token_lookup: dict[str, str] = {}

    def _create_tunnel(self) -> str:
        """Create a Tunnel.

        Returns:
            Cloudflare tunnel ID.
        """
        name = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
        name = name + "".join(random.choices(string.ascii_letters + string.digits, k=4))
        logger.info("creating tunnel %s", name)
        response = self._session.post(
            self._endpoint, json={"name": name, "config_src": "cloudflare"}, timeout=10
        )
        response.raise_for_status()
        tunnel_id = response.json()["result"]["id"]
        logger.info("created tunnel %s", tunnel_id)
        self._created_tunnels.append(tunnel_id)
        return tunnel_id

    def _get_tunnel_token(self, tunnel_id: str) -> str:
        """Get tunnel token.

        Args:
            tunnel_id: cloudflare tunnel ID.

        Returns:
            Tunnel token.
        """
        response = self._session.get(f"{self._endpoint}/{tunnel_id}/token", timeout=10)
        response.raise_for_status()
        tunnel_token = response.json()["result"]
        self._tunnel_token_lookup[tunnel_token] = tunnel_id
        return tunnel_token

    def create_tunnel_token(self) -> str:
        """Create a tunnel and return its tunnel token.

        Returns:
            Tunnel token.
        """
        tunnel_id = self._create_tunnel()
        return self._get_tunnel_token(tunnel_id)

    def _get_tunnel_status(self, tunnel_id: str) -> str:
        """Get tunnel status.

        Args:
            tunnel_id: cloudflare tunnel ID.

        Returns:
            Tunnel status.
        """
        response = self._session.get(f"{self._endpoint}/{tunnel_id}", timeout=10)
        response.raise_for_status()
        return response.json()["result"]["status"]

    def get_tunnel_status_by_token(self, tunnel_token: str) -> str:
        """Get tunnel status by its tunnel token.

        Args:
            tunnel_token: cloudflare tunnel token.

        Returns:
            Tunnel status.
        """
        tunnel_id = self._tunnel_token_lookup[tunnel_token]
        return self._get_tunnel_status(tunnel_id)

    def delete_tunnel(self, tunnel_id: str) -> None:
        """Delete a tunnel.

        Args:
            tunnel_id: cloudflare tunnel ID.
        """
        logger.info("deleting tunnel %s", tunnel_id)
        response = self._session.delete(f"{self._endpoint}/{tunnel_id}", timeout=10)
        response.raise_for_status()


@pytest.fixture(scope="module")
def cloudflare_api():
    """Cloudflare API fixture."""
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    assert account_id
    api_token = os.environ["CLOUDFLARE_API_TOKEN"]
    assert api_token
    api = CloudflareAPI(account_id=account_id, api_token=api_token)

    yield api

    for tunnel_id in api._created_tunnels:
        try:
            logger.info("deleting tunnel %s", tunnel_id)
            api.delete_tunnel(tunnel_id)
        except requests.exceptions.RequestException:
            logger.exception("failed to delete tunnel %s", tunnel_id)
