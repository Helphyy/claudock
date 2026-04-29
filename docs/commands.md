# Commands reference

`claudock <verb> [options]`. Run `claudock` with no arguments to see the dashboard (banner + container table + cheatsheet).

## Global flags

| Flag | Effect |
|------|--------|
| `-v`, `--verbose` | Verbose output |
| `-d`, `--debug` | Debug output (implies `--verbose`) |
| `-q`, `--quiet` | Minimal output |
| `-y`, `--yes` | Auto-confirm prompts |

## Container lifecycle

| Verb | Description |
|------|-------------|
| `claudock start [name] [path]` | Create or attach to a named container. See [flags.md](flags.md). |
| `claudock stop [name]` | Stop a running container. Selector if no name. |
| `claudock restart [name]` | Restart a container. |
| `claudock exec <name> <cmd...>` | Run a one-off command. |
| `claudock remove [name]` | Remove a container. `-f` skips confirmation. |
| `claudock info` | Table view of all Claudock containers. |
| `claudock logs [name]` | List recorded asciinema sessions for a container. |

## Image management

| Verb | Description |
|------|-------------|
| `claudock install [image]` | Alias of `image install`. |
| `claudock image list` | List official variants and any local custom images. |
| `claudock image install [image]` | Pull a variant or full image ref. |
| `claudock image install-all` | Pull every official variant from the registry. |
| `claudock image update [image]` | Re-pull to refresh the tag. |
| `claudock image remove <image>` | `docker rmi`. `-f` to force. |
| `claudock image build <path>` | Build a local Dockerfile and tag it as a Claudock image. |

The `image` argument accepts either a variant name (`dev`, `cloud`, ...) or a full ref (`ghcr.io/foo/bar:tag`).

## Profiles

| Verb | Description |
|------|-------------|
| `claudock profile list` | List profiles. |
| `claudock profile create [name]` | Create a profile dir under `~/.claudock/profiles/`. |
| `claudock profile remove [name]` | Remove a profile. `-f` skips confirmation. |
| `claudock profile show [name]` | Inspect a profile (token presence, last login, etc.). |

See [profiles.md](profiles.md) for the full multi-profile workflow.

## Config

| Verb | Description |
|------|-------------|
| `claudock config show` | Print the resolved config (global + project). |
| `claudock config path` | Print the path to `~/.claudock/config.yml`. |
| `claudock config edit` | Open the config in `$EDITOR`. |

## Misc

| Verb | Description |
|------|-------------|
| `claudock version` | Print the Claudock CLI version. |

## Selectors

When a verb takes an optional `name` and you omit it, Claudock prints a Rich table of candidates and prompts you to pick one. This works for `stop`, `restart`, `remove`, `logs`, `profile remove`, `profile show`.
