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


def get_proxy_env() -> dict:
    http_proxy = get_config("http-proxy")
    https_proxy = get_config("https-proxy")
    no_proxy = get_config("no-proxy")
    env = {}
    if http_proxy:
        env["HTTP_PROXY"] = http_proxy
        env["http_proxy"] = http_proxy
    if https_proxy:
        env["HTTPS_PROXY"] = https_proxy
        env["https_proxy"] = https_proxy
    if no_proxy:
        env["NO_PROXY"] = no_proxy
        env["no_proxy"] = no_proxy
    return env


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
                **get_proxy_env(),
                "TUNNEL_TOKEN": token,
            },
        )


if __name__ == "__main__":
    main()
