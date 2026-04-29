# Networking

Claudock uses Docker's networking stack. By default each container gets its own `bridge` network, isolated from your host except through explicit port maps.

## Modes

```bash
claudock start my-app --cwd --network bridge          # default
claudock start my-app --cwd --network host            # share host net stack
claudock start my-app --cwd --network none            # no network at all
claudock start my-app --cwd --network my-custom-net   # any pre-existing Docker network
```

| Mode | When to use |
|------|-------------|
| `bridge` | Default. Container has its own IP; reach the host with `host.docker.internal` (or the bridge gateway, usually `172.17.0.1`). |
| `host` | When you want the container to bind directly to host ports (e.g. dev server on `:3000` reachable as `localhost:3000`). Less isolation. |
| `none` | Air-gapped. Useful for one-off code-execution sandboxes you don't trust. |
| `<name>` | Pre-existing Docker network, e.g. one shared with a `docker compose` stack. Lets the container reach `db`, `redis`, etc. by service name. |

## Port forwarding

```bash
claudock start api --cwd -p 8000:8000 -p 5432:5432
```

The `-p` flag is `HOST:CONT[/PROTO]`, repeatable. Same syntax as `docker run -p`. If the container also opens code-server (`--vscode`), Claudock forwards `127.0.0.1:8080` automatically.

## Reaching the host from inside

| Mode | How |
|------|-----|
| `bridge` | `host.docker.internal` (works on Linux 20.10+ via host-gateway) or the bridge gateway IP. |
| `host` | `localhost` is the host. |
| `none` | You can't. |

## DNS

Containers inherit the host's resolv.conf via Docker's DNS. If your VPN's DNS is set on the host, it usually flows through. Diagnose with:

```bash
claudock exec my-app cat /etc/resolv.conf
claudock exec my-app dig example.com
```

## Common pitfalls

- **`localhost` from inside `bridge` doesn't reach my host service.** Use `host.docker.internal` or `--network host`.
- **Two Claudock containers can't see each other.** Put them on the same Docker network: `docker network create claudock-net && claudock start a --network claudock-net && claudock start b --network claudock-net`. Or use `host`.
- **Corporate proxy.** Set `HTTP_PROXY`/`HTTPS_PROXY` via `-e` flags or in `~/.claudock/config.yml`'s `env` section.
- **VPN DNS leak.** Some VPNs require host-only DNS resolution. `--network host` is the simplest fix.
