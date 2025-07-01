# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""charmed-cloudflared snap tests."""

import logging
import time

logger = logging.getLogger(__name__)


def wait_for_tunnel_healthy(cloudflare_api, tunnel_token):
    """Wait for a cloudflared tunnel to become healthy.

    Args:
        cloudflare_api: Cloudflare API object.
        tunnel_token: Tunnel token.

    Raises:
        TimeoutError: If tunnel fails to become healthy in given timeout.
    """
    deadline = time.time() + 300
    while time.time() < deadline:
        tunnel_status = cloudflare_api.get_tunnel_status_by_token(tunnel_token)
        logger.info("tunnel status: %s", tunnel_status)
        if tunnel_status != "healthy":
            time.sleep(10)
        else:
            return
    raise TimeoutError("timeout waiting for tunnel healthy")


def test_tunnel_token_config(
    cloudflare_api, charmed_cloudflared_snap, run, pytestconfig
):
    tunnel_token = cloudflare_api.create_tunnel_token()
    cmd = [
        "sudo",
        "snap",
        "set",
        charmed_cloudflared_snap,
        f"tunnel-token={tunnel_token}",
        "metrics-port=39000",
    ]
    https_proxy = pytestconfig.getoption("--https-proxy")
    if https_proxy:
        cmd.append(f"https-proxy={https_proxy}")
    run(cmd, redact=tunnel_token)
    run(
        [
            "sudo",
            "cp",
            "/etc/resolv.conf",
            f"/var/snap/{charmed_cloudflared_snap}/current/etc/",
        ]
    )
    run(
        [
            "sudo",
            "mkdir",
            "-p",
            f"/var/snap/{charmed_cloudflared_snap}/current/etc/ssl/certs",
        ]
    )
    run(
        [
            "sudo",
            "cp",
            "/etc/ssl/certs/ca-certificates.crt",
            f"/var/snap/{charmed_cloudflared_snap}/current/etc/ssl/certs/ca-certificates.crt",
        ]
    )
    run(
        ["sudo", "snap", "start", "--enable", f"{charmed_cloudflared_snap}.cloudflared"]
    )
    wait_for_tunnel_healthy(cloudflare_api, tunnel_token)
