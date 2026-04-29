"""Docker daemon access through docker-py."""

from __future__ import annotations

from functools import lru_cache

import docker
from docker import DockerClient
from docker.errors import DockerException

from claudock.exceptions import DockerUnavailableError


@lru_cache(maxsize=1)
def get_client() -> DockerClient:
    try:
        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        raise DockerUnavailableError(
            "Cannot reach the Docker daemon. Is it running?"
        ) from exc
    return client
