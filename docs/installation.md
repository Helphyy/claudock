# Installation

## Requirements

- Python 3.11+
- Docker Engine 24+ (the daemon must be running and your user must be in the `docker` group)
- Linux or macOS

## Install the CLI

### Recommended: pipx from GitHub

```bash
pipx install git+https://github.com/helphyy/claudock.git
```

`pipx` installs the CLI into its own isolated venv and exposes the `claudock` entrypoint on your `PATH` without polluting the system Python. Install pipx itself with `apt install pipx` (Debian/Ubuntu), `brew install pipx`, or `python3 -m pip install --user pipx && pipx ensurepath`.

### Alternative: pipx from a local clone

```bash
git clone https://github.com/helphyy/claudock.git
cd claudock
pipx install .
```

### Development install (editable, with test deps)

```bash
git clone https://github.com/helphyy/claudock.git
cd claudock
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### Upgrade

```bash
pipx upgrade claudock
```

### Uninstall

```bash
pipx uninstall claudock
```

## Verify

```bash
claudock --version
claudock              # opens the dashboard
```

## Pull a Claudock image

The default image is `ghcr.io/helphyy/claudock-dev:latest`.

```bash
claudock image install dev          # variant shorthand
claudock image install              # uses the default from config
claudock image install-all          # pull all seven variants
```

The 7 variants live on the public GHCR namespace: `minimal`, `dev`, `cloud`, `security`, `data`, `doc`, `full`. See [images.md](images.md) for the full breakdown.

## First profile

Create your first Claude auth profile (a directory under `~/.claudock/profiles/`):

```bash
claudock profile create personal
```

The directory is bind-mounted into every container that uses this profile. The first `claude` invocation inside the container will trigger the OAuth flow; the credentials persist on the host.
