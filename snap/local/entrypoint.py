#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import subprocess


def run_cloudflared():
    tunnel_token = subprocess.check_output(
        ["snapctl", "get", "tunnel-token"], encoding="ascii"
    ).strip()
    if not tunnel_token:
        raise RuntimeError("tunnel-token not configured")
    env = {
        "TUNNEL_TOKEN": tunnel_token,
    }
    os.setgroups([])
    os.setregid(584792, 584792)
    os.setreuid(584792, 584792)
    snap_dir = os.environ["SNAP"]
    subprocess.check_call(
        [
            os.path.join(snap_dir, "usr/bin/cloudflared"),
            "tunnel",
            "--no-autoupdate",
            "run",
        ],
        env=env,
    )


if __name__ == "__main__":
    run_cloudflared()
