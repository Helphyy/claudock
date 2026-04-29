# Troubleshooting

## "permission denied while trying to connect to the Docker daemon socket"

Your user isn't in the `docker` group. Fix:

```bash
sudo usermod -aG docker $USER
newgrp docker             # or log out/in
```

## "Image not found"

Pull it explicitly:

```bash
claudock image install dev
```

Or build from local Dockerfiles:

```bash
cd ../claudock-images
make build-dev
```

## OAuth login loop / Claude won't accept my creds

Inside the container, blow away the auth state and retry:

```bash
rm -rf /root/.claude/.credentials*
claude
```

The host-side profile (`~/.claudock/profiles/<name>/`) follows.

## VSCode in browser asks for a password

Code-server picks a random password if `~/.config/code-server/config.yaml` doesn't exist. Claudock's `--vscode` writes a config with auth disabled on `127.0.0.1` (loopback only). If you tunneled the port off-machine, **add auth back** before doing so.

## Headed Chromium / Firefox crashes with "cannot open display"

You forgot `--x11`, or your host has Wayland and `xhost` doesn't permit the container. On Wayland:

```bash
xhost +SI:localuser:root
```

(reverts on reboot).

## "Operation not permitted" running `vault` / `consul` / `nomad` 2.x

HashiCorp 2.x binaries ship with `cap_ipc_lock=ep` file-cap. Container's capability bounding set blocks them. Already fixed in `claudock-cloud` and `claudock-full` (a `setcap -r` runs at build). If you build a custom image that installs HashiCorp tools, mirror the fix:

```dockerfile
RUN for b in vault consul nomad; do \
      setcap -r "/usr/bin/$b" 2>/dev/null || true ; \
    done
```

## Container starts but exits immediately

Check the entrypoint logs:

```bash
docker logs claudock-<name>
```

Common causes: `--shell bash` on an image that doesn't have bash (use zsh), or a syntax error in your `.zshrc` mounted into the container.

## I want to wipe everything and start fresh

```bash
claudock info                          # see what's there
docker rm -f $(docker ps -aq --filter name=claudock-)
docker rmi $(docker images -q --filter reference='claudock-*')
rm -rf ~/.claudock
```

(Profiles and config will be gone. Make a backup first if you care.)

## Where do I file bugs?

GitHub issues: <https://github.com/helphyy/claudock/issues>. Include:

- `claudock --version`
- `docker version`
- Full command you ran
- What you expected vs. what happened
- Logs from `claudock --debug <verb>`
