"""Internal claudock exceptions."""

from __future__ import annotations


class ClaudockError(Exception):
    """Base claudock error."""


class ContainerNotFoundError(ClaudockError):
    """Named container not found."""


class ContainerAlreadyExistsError(ClaudockError):
    """A container with that name already exists."""


class ImageNotFoundError(ClaudockError):
    """Docker image not found locally."""


class ConfigError(ClaudockError):
    """User configuration error."""


class DockerUnavailableError(ClaudockError):
    """Docker daemon unreachable."""
