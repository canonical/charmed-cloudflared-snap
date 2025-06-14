#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import subprocess


def get_config(config: str) -> str:
    return subprocess.check_output(
        ["snapctl", "get", config], encoding="ascii"
    ).strip()


def get_token() -> str | None:
    return get_config("tunnel-token")


def get_metrics_port() -> int | None:
    port = get_config("metrics-port")
    return int(port) if port else None


def main():
    os.setgroups([])
    os.setregid(584792, 584792)
    os.setreuid(584792, 584792)
    token = get_token()
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
