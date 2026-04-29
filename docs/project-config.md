# Project config: `.claudock.yml`

A `.claudock.yml` file at the root of your workdir lets you bake in defaults so you don't have to type the same `claudock start` flags every time.

## Resolution order

For a given `claudock start`, values are merged with this precedence (top wins):

1. CLI flags
2. `.claudock.yml` in the workdir (when `--cwd` or an explicit path is given)
3. Global `~/.claudock/config.yml`
4. Built-in defaults

## Schema

All keys live under `defaults:` and are optional. The shape matches the `ProjectConfig` dataclass; flat keys, no nested sections.

```yaml
# ~/code/my-app/.claudock.yml

defaults:
  image: dev                # variant name (minimal/dev/cloud/security/data/doc/full)
                            # or full ref (ghcr.io/helphyy/claudock-dev:latest)
  profile: work             # Claude auth profile name
  network: bridge           # bridge | host | none | <docker-net>
  shell: zsh                # empty -> launches `claude` directly instead of a shell
  hostname: my-app

  # Booleans, all default to false
  log: false                # if true, --log is implied (asciinema recording)
  x11: false                # if true, --x11 is implied (X11 forwarding)
  vscode: false             # if true, --vscode is implied (code-server on 127.0.0.1:8080)
  docker: false             # if true, --docker is implied (DANGEROUS: root on host)

  # Git + SSH
  git: git@github.com:you/my-app.git   # clone URL, auto-enables ssh
  ssh: true                            # true = forward ~/.ssh, or a path string

  # Linux capabilities (additive with CLI --cap)
  caps: [SYS_PTRACE]

  # Reasoning effort forwarded to Claude Code (low/medium/high/max)
  effort: max

  # Env vars (additive with CLI -e); CLI keys win on conflict
  env:
    STAGE: dev
    HTTP_PROXY: http://proxy:3128

  # Extra bind mounts (additive with CLI -V), HOST:CONT[:MODE]
  volumes:
    - ~/datasets:/workspace/datasets:ro
    - /shared:/cache:ro

  # Extra port maps (additive with CLI -p), HOST:CONT[/PROTO]
  ports:
    - 8000:8000
    - 5432:5432
```

## Field reference

| Key | Type | Notes |
|-----|------|-------|
| `image` | string | Variant name or full image ref. Same expansion as `claudock image install`. |
| `profile` | string | Claude auth profile. Created on the fly if missing. |
| `network` | string | `bridge` / `host` / `none` / a Docker network name. |
| `shell` | string | Shell to launch on attach. Empty string -> launch `claude` directly. |
| `hostname` | string | Container hostname. Defaults to the container name. |
| `log` | bool | Equivalent of `--log`. |
| `x11` | bool | Equivalent of `--x11`. |
| `vscode` | bool | Equivalent of `--vscode`. Port stays at 8080 (no override here). |
| `docker` | bool | Equivalent of `--docker`. **DANGER**: grants root on host. |
| `git` | string | Equivalent of `--git URL`. Auto-implies `ssh: true`. |
| `ssh` | bool or string | `true` -> mount `~/.ssh`. A string -> mount that directory. |
| `caps` | list of string | Extra Linux capabilities, additive with CLI `--cap`. |
| `effort` | string | `low` / `medium` / `high` / `max`. Forwarded to Claude Code. |
| `env` | dict | Extra env vars, additive with CLI `-e`. CLI wins on key conflicts. |
| `volumes` | list of string | Extra bind mounts, additive with CLI `-V`. Format `HOST:CONT[:MODE]`. Host paths are resolved (no `..` traversal). |
| `ports` | list of string | Extra port maps, additive with CLI `-p`. Format `HOST:CONT[/PROTO]`. |

## Use cases

- One project pinned to `claudock-data` for ML notebooks; another to `claudock-cloud` for IaC.
- Shared port mappings for the team's local stack.
- Auto-enable `--vscode` for projects where you always want code-server.
- Force `effort: high` on a heavy debugging project, `effort: low` on a quick scratchpad.

## Editing

Just open `.claudock.yml` in the project root with any text editor. Claudock re-reads it on every `start`.

## Validation

`claudock config show` prints the resolved configuration, merging globals + project. Run it from inside the project to sanity-check what Claudock will actually do.
