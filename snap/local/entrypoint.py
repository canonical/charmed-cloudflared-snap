#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import atexit
import logging
import os
import pathlib
import subprocess
import signal
import time
import typing

METRICS_PORT_START = 15300
TERMINATION_GRACE_SECONDS = 5

logger = logging.getLogger(__name__)


class Cloudflared:
    def __init__(self, token, metrics_port):
        self.token = token
        self.metrics_port = metrics_port
        self.process: subprocess.Popen | None = None
        self.restart()

    def restart(self):
        assert self.process is None or self.process.poll() is not None
        self.process = subprocess.Popen(
            [
                os.path.join(os.environ["SNAP"], "usr/bin/cloudflared"),
                "tunnel",
                "--no-autoupdate",
                "--metrics",
                f"127.0.0.1:{self.metrics_port}",
                "--protocol",
                "http2",
                "run",
            ],
            env={
                "TUNNEL_TOKEN": self.token,
            },
        )


def get_tokens() -> list[str]:
    tokens = subprocess.check_output(["snapctl", "get", "tokens"], encoding="ascii")
    return [token.strip() for token in tokens.split(",") if token.strip()]


def shutdown(procs: typing.Iterable[Cloudflared]):
    if not procs:
        return
    logger.info(
        "shutting down cloudflared processes: %s", [p.process.pid for p in procs]
    )
    for proc in procs:
        proc.process.terminate()
    termination_deadline = time.time() + TERMINATION_GRACE_SECONDS
    for proc in procs:
        if time.time() < termination_deadline:
            try:
                proc.process.wait(timeout=termination_deadline - time.time())
            except subprocess.TimeoutExpired:
                proc.process.kill()
        else:
            if proc.process.poll() is None:
                proc.process.kill()


def reload(procs: list[Cloudflared], tokens: list[str]) -> list[Cloudflared]:
    logger.info("reloading cloudflared tunnel tokens")
    shutdown_procs = []
    old_tokens = [p.token for p in procs]
    if set(old_tokens) == set(tokens):
        return procs
    new_tokens = [t for t in tokens if t not in old_tokens]
    new_procs = []
    for proc in procs:
        if proc.token not in tokens:
            shutdown_procs.append(proc)
            continue
        # ensure that metrics ports are always continuous and start at METRICS_PORT_START
        if proc.metrics_port >= METRICS_PORT_START + len(tokens):
            shutdown_procs.append(proc)
            new_tokens.append(proc.token)
            continue
        new_procs.append(proc)
    shutdown(shutdown_procs)
    for token in new_tokens:
        for metrics_port in range(METRICS_PORT_START, METRICS_PORT_START + len(tokens)):
            if metrics_port not in [p.metrics_port for p in new_procs]:
                break
        new_procs.append(Cloudflared(token=token, metrics_port=metrics_port))
    return new_procs


def restart(procs: list[Cloudflared], backoff=5) -> None:
    for proc in procs:
        if proc.process.poll() is not None:
            logger.info("restarting cloudflared process: %s", proc.process.pid)
            proc.restart()
    time.sleep(backoff)


def main():
    pid_file = pathlib.Path(os.environ["SNAP_COMMON"]) / "run" / "services.pid"
    pid_file.parent.mkdir(exist_ok=True)
    os.chown(pid_file.parent, 584792, 584792)
    os.setgroups([])
    os.setregid(584792, 584792)
    os.setreuid(584792, 584792)
    atexit.register(lambda: pid_file.unlink(missing_ok=True))
    signal.pthread_sigmask(
        signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGCHLD, signal.SIGHUP}
    )
    pid_file.write_text(str(os.getpid()))
    procs = [
        Cloudflared(token=token, metrics_port=metrics_port)
        for metrics_port, token in enumerate(get_tokens(), start=METRICS_PORT_START)
    ]
    try:
        while True:
            sig = signal.sigwaitinfo({signal.SIGTERM, signal.SIGCHLD, signal.SIGHUP})
            match sig.si_signo:
                case signal.SIGTERM:
                    break
                case signal.SIGCHLD:
                    restart(procs)
                case signal.SIGHUP:
                    procs = reload(procs, get_tokens())
    finally:
        shutdown(procs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
