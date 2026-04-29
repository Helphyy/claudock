# claudock

A secure containerized wrapper for [Claude Code](https://docs.claude.com/en/docs/claude-code).

Spins up Claude Code inside named, persistent Docker containers (one per project) where workspace, shell history, installed packages and Claude credentials are all preserved between sessions.

## Status

Alpha, in active development.

## Installation

```bash
pipx install git+https://github.com/helphyy/claudock.git
```

Then pull at least one image:

```bash
claudock image install dev    # or any of: minimal, dev, cloud, security, data, doc, full
```

See [docs/installation.md](docs/installation.md) for requirements (Python 3.11+, Docker 24+) and alternative install methods.

## Concepts

- **Named, persistent containers**: `claudock start my-project` creates (or restarts) a named container that survives across sessions. Your shell history, ad-hoc installs and Claude auth are all there next time.
- **Multi-profile Claude auth**: `~/.claudock/profiles/<name>/.claude/` is bind-mounted at `/root/.claude/`. Each profile is one credentials store (one OAuth login, one subscription). Multiple containers using the same profile share the auth state; different profiles are fully isolated.
- **Seven layered images**: `minimal`, `dev`, `cloud`, `security`, `data`, `doc`, `full`. All ship Claude Code (native binary), code-server with the official `Anthropic.claude-code` extension, zsh + plugins, asciinema, Firefox + Chromium. See [docs/images.md](docs/images.md).
- **Security**: Docker's default capabilities, `no-new-privileges`, no Docker socket by default, never `--privileged`.

## CLI verbs

```
claudock                                 Dashboard (banner + tables + cheatsheet)
claudock start [name] [path] [options]   Create / start / attach a container
claudock stop [name]                     Stop (selector if no name)
claudock restart [name]
claudock exec <name> <cmd...>            Run a command inside a container
claudock info                            List Claudock containers
claudock remove [name]                   Remove a container (selector)
claudock install [image]                 Pull a Docker image
claudock logs [name]                     List recorded sessions
claudock profile list                    List Claude auth profiles
claudock profile create [name]           Create an empty profile
claudock profile show [name]             Profile details (selector)
claudock profile remove [name] [-f]      Remove a profile (selector)
claudock config show                     Show the resolved config
claudock config path                     Show the config file path
claudock config edit                     Open the config in $EDITOR
claudock version
```

### `start` options

```
--cwd                       Use the current cwd as /workspace
--image IMAGE               Override the default image
-s, --shell SHELL           Launch a shell instead of claude (bash, zsh)
--network MODE              bridge, host, none, or a Docker network name
--hostname NAME             Custom hostname (default: container name)
--profile NAME              Claude auth profile (default: config default_profile)
-e, --env KEY=VAL           Inject env var (repeatable)
-V, --volume H:C[:MODE]     Extra mount (repeatable)
-p, --port HOST:CONT[/PROTO] Expose a port (repeatable)
--cap CAP_NAME              Add a Linux capability (repeatable)
--tmp                       Disposable container, removed on exit
--log                       Record the shell session (asciinema)
--x11                       Share the host X server (GUI / headed browsers)
--no-update-fs              Skip the chgrp/setgid on /workspace
--vscode                    Start code-server (FOSS VSCode) at startup
--vscode-port PORT          Host port for code-server (default 8080, 127.0.0.1)
-g, --git URL               Clone a git URL into /workspace (auto-enables --ssh)
--ssh [DIR]                 Forward an SSH directory (default ~/.ssh) + ~/.gitconfig + SSH_AUTH_SOCK
--docker                    DANGEROUS: bind /var/run/docker.sock (DooD). Gives root on host.
```

> ⚠ `--docker` mounts the host Docker socket so the container can spawn sibling
> containers via the host's daemon. **Anything inside (Claude included) gets
> effective root on your host** (`docker run -v /:/host` and game over). Use
> only with code you fully trust. Same threat tier as `--privileged`.

### Examples

```bash
# Persistent container named "monrepo" on the current cwd
claudock start monrepo --cwd

# Disposable container with an API key and one exposed port
claudock start review --tmp -e ANTHROPIC_API_KEY=sk-... -p 3000:3000

# Container with a shared pnpm cache and SYS_PTRACE for gdb/strace
claudock start backend --cwd -V ~/.cache/pnpm:/root/.cache/pnpm --cap SYS_PTRACE

# Host networking to debug a local service
claudock start hostnet --cwd --network host

# Separate perso / pro profiles
claudock profile create perso
claudock profile create pro
claudock start side-project --cwd --profile perso
claudock start app-client --cwd --profile pro

# Record a session for audit/replay
claudock start audit --cwd --log
claudock logs audit
asciinema play ~/.claudock/logs/audit/<timestamp>.cast

# Clone a repo + forward your ssh-agent at start
claudock start my-project --git git@github.com:user/repo.git
# Repo cloned into /workspace, ~/.ssh + ~/.gitconfig mounted ro,
# SSH_AUTH_SOCK forwarded → push/pull works with your host key.

# VSCode in the browser (code-server, 27 extensions including Claude Code)
claudock start my-project --cwd --vscode

# GUI / headed browser (Playwright, Chromium...) via X11
xhost +local:                       # once on the host
claudock start gui --cwd --x11
# Inside the container:
apt-get update && apt-get install -y chromium
chromium                            # renders on your host display
```

## Project config: `.claudock.yml`

If a `.claudock.yml` file exists at the root of the workspace passed to
`start`, its defaults are merged on top of the global config (CLI flags still
win). Schema:

```yaml
defaults:
  image: claudock-base:dev
  profile: pro
  network: bridge        # bridge | host | none | <docker-net>
  shell: zsh             # empty = launch claude directly
  hostname: my-box
  log: false
  x11: false
  vscode: false
  git: git@github.com:user/repo.git
  ssh: true              # or "/path/to/.ssh-acme"
  caps: [SYS_PTRACE]
  env:
    HTTP_PROXY: http://proxy:3128
  volumes:
    - /shared:/cache:ro
  ports:
    - "3000:3000"
```

Final resolution: CLI flag > `.claudock.yml` > `~/.claudock/config.yml` > built-in.

## FS permissions (host ↔ container)

When a container is created the wrapper runs:
- `chgrp <host_gid> /workspace` (workspace group is your host group)
- `chmod g+rwXs /workspace` (setgid → new files inherit the group)
- `umask 002` is forced in every exec and in `/etc/profile.d` (default mode 0664)

End result: a file created by root inside the container shows up as
`root:<host_gid> 0664`, so your host user can read/write through the group.
`--no-update-fs` skips this behaviour.

## Documentation

Full user guide under [`docs/`](docs/README.md):

- [Installation](docs/installation.md), [Quickstart](docs/quickstart.md)
- [Commands reference](docs/commands.md), [Start flags](docs/flags.md)
- [Profiles](docs/profiles.md), [Images](docs/images.md), [Project config](docs/project-config.md)
- [Filesystem](docs/filesystem.md), [Networking](docs/networking.md)
- [Troubleshooting](docs/troubleshooting.md)

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
claudock --help
```

## Acknowledgements

Heavily inspired by [Exegol](https://github.com/ThePorgs/Exegol), the
containerized offensive security environment. Claudock borrows its core ideas
(named persistent containers, profile-based credential mounts, image-management
CLI) and adapts them to running Claude Code safely on any project.

## License

GPLv3
