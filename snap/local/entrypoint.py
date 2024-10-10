#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import subprocess


def get_tokens() -> str | None:
    token = subprocess.check_output(
        ["snapctl", "get", "tunnel-token"], encoding="ascii"
    )
    return token.strip()


def get_metrics_port() -> int | None:
    port = subprocess.check_output(["snapctl", "get", "metrics-port"], encoding="ascii")
    return int(port.strip()) if port.strip() else None


def main():
    os.setgroups([])
    os.setregid(584792, 584792)
    os.setreuid(584792, 584792)
    token = get_tokens()
    metrics_port = get_metrics_port()
    if metrics_port and token:
        subprocess.check_call(
            [
                os.path.join(os.environ["SNAP"], "usr/bin/cloudflared"),
                "tunnel",
                "--no-autoupdate",
                "--metrics",
                f"127.0.0.1:{metrics_port}",
                "--protocol",
                "http2",
                "run",
            ],
            env={
                "TUNNEL_TOKEN": token,
            },
        )


if __name__ == "__main__":
    main()
