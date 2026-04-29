# `claudock start` flags

Full reference. Every flag here can also be set via project config (see [project-config.md](project-config.md)).

## Synopsis

```bash
claudock start [name] [path] [options]
```

- `name`: container name. Optional (defaults to a sanitized basename of the workdir).
- `path`: host workdir to mount at `/workspace`. Optional.
- `--cwd`: use the current cwd as the workdir.

## Container identity

| Flag | Default | Effect |
|------|---------|--------|
| `--image <ref>` | from config | Override image (variant or full ref). |
| `--hostname <h>` | container name | Container hostname. |
| `--tmp` | off | Disposable container, removed on exit. |

## Profile and shell

| Flag | Default | Effect |
|------|---------|--------|
| `--profile <name>` | `default_profile` | Pick a Claude auth profile. |
| `-s`, `--shell <bin>` | `zsh` | Shell to launch. Empty string launches `claude` directly. |

## Filesystem

| Flag | Default | Effect |
|------|---------|--------|
| `-V`, `--volume HOST:CONT[:MODE]` | none | Extra bind mount (repeatable). |
| `--no-update-fs` | off | Skip `chgrp/setgid` on `/workspace`. See [filesystem.md](filesystem.md). |

## Networking

| Flag | Default | Effect |
|------|---------|--------|
| `--network <mode>` | `bridge` | `bridge`, `host`, `none`, or a Docker network name. |
| `-p`, `--port HOST:CONT[/PROTO]` | none | Publish a port (repeatable). |

## Environment

| Flag | Default | Effect |
|------|---------|--------|
| `-e`, `--env KEY=VAL` | none | Inject an env var (repeatable). |

## Capabilities

| Flag | Default | Effect |
|------|---------|--------|
| `--cap CAP_NAME` | none | Add a Linux capability. Repeatable. e.g. `--cap SYS_PTRACE`. |

## Recording

| Flag | Default | Effect |
|------|---------|--------|
| `--log` | off | Record the shell session with asciinema, stored under `~/.claudock/logs/<container>/`. |

## GUI / X11

| Flag | Default | Effect |
|------|---------|--------|
| `--x11` | off | Forward `/tmp/.X11-unix` + `DISPLAY` + `XAUTHORITY` so headed browsers (Chromium, Firefox) and Playwright run inside the container display on your host screen. **Trust the code you run.** |

## VSCode in browser

| Flag | Default | Effect |
|------|---------|--------|
| `--vscode` | off | Start `code-server` on attach. Default port `127.0.0.1:8080`. |
| `--vscode-port <n>` | `8080` | Alternative host port. |

## Git and SSH

| Flag | Default | Effect |
|------|---------|--------|
| `-g`, `--git URL` | none | Clone `URL` into `/workspace` after creation (auto-enables `--ssh`). |
| `--ssh [DIR]` | off | Forward an SSH directory (default `~/.ssh`, or a custom path). Also forwards `~/.gitconfig` and `SSH_AUTH_SOCK`. |

## Docker-out-of-Docker

| Flag | Default | Effect |
|------|---------|--------|
| `--docker` | off | Mount the host Docker socket. **DANGER:** equivalent to root on the host. Only use for trusted code. Claudock prints a warning panel before starting. |

## Claude Code pass-through

These flags are forwarded to the `claude` invocation that runs on attach. Ignored when `--shell` is set (you launch `claude` yourself).

| Flag | Default | Effect |
|------|---------|--------|
| `--dangerously-skip-permissions`, `--yolo` | off | No per-tool permission prompts inside Claude. Safe only because /workspace is the container's isolation boundary. `--yolo` is the short alias. |
| `--effort {low,medium,high,max}` | from `config.default_effort` (max) | Reasoning effort level forwarded to Claude. Default comes from `~/.claudock/config.yml` or `.claudock.yml`. |
| `-c`, `--continue` | off | Continue Claude's most recent conversation. Skips the in-container picker. |
| `-r`, `--resume ID` | none | Resume a specific Claude session by ID. Skips the picker. |
| `--model NAME` | from Claude config | Pick the model: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`, etc. |
| `--permission-mode MODE` | none | One of `default`, `acceptEdits`, `plan`, `bypassPermissions`. Softer alternative to `--dangerously-skip-permissions`. |
| `--print PROMPT` | none | Non-interactive: run Claude with `PROMPT` and exit. Makes `claudock start` usable in CI/scripts. |
| `--add-dir PATH` | none | Extra directory Claude can read from (in addition to `/workspace`). Repeatable. |
| `--ide` | off | Tell Claude to connect to the IDE. Pair with `--vscode` for code-server integration. |

## Examples

```bash
# Full-featured local dev session
claudock start my-app --cwd \
  --image dev --profile work \
  --vscode --ide --ssh --git git@github.com:me/my-app.git \
  -p 8000:8000

# Throwaway browser sandbox (X11 + Chromium)
claudock start --tmp --x11 --image minimal

# Pentest workshop with extra cap
claudock start ctf --cwd --image security --cap NET_RAW

# Resume the last Claude conversation immediately
claudock start my-app --cwd -c --model claude-opus-4-7

# Non-interactive scripted run, plan mode, extra read dir
claudock start audit --cwd \
  --permission-mode plan \
  --add-dir /etc/configs \
  --print "Audit /workspace and report"
```
