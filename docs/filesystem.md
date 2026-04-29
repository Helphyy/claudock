# Filesystem: bind mounts, ownership, umask

Claudock containers run as **root** by design (so `apt install` Just Works during a session). The trick to keeping host-side files comfortable is a small set of permission rules applied automatically.

## Default mounts

| Container path | Host source | Mode | Purpose |
|----------------|-------------|------|---------|
| `/workspace` | the path you passed (or `--cwd`) | `rw` | Your project files. |
| `/root/.claude` | `~/.claudock/profiles/<profile>/.claude` | `rw` | Claude credentials + conversations. |
| `/var/log/claudock-sessions` | `~/.claudock/logs/<container>` | `rw` | Asciinema recordings (when `--log`). |

Add as many extra mounts as you need with `-V HOST:CONT[:MODE]` (repeatable).

## Why `--update-fs` exists

When root in a container creates a file in `/workspace`, by default it shows up on the host as `root:root 0644`. Your unprivileged host user can read it but not write it without `sudo`. That's annoying.

Claudock's default behaviour (`--update-fs` is implicitly on) does this once when a container starts:

```bash
chgrp <host_gid> /workspace          # /workspace's group = your host group
chmod g+rwXs    /workspace           # group can rw + setgid for inheritance
```

And every interactive shell sources `/etc/profile.d/claudock-umask.sh`:

```bash
umask 002                             # new files mode 0664, dirs 2775
```

End result: a file created by root inside the container shows up on the host as `root:<host_gid> 0664`. Your host user reads/writes it through the group. No `sudo` needed.

## Opting out

Pass `--no-update-fs` to skip `chgrp/setgid`. Files will be `root:root` on the host. Use this if your workdir is owned by root or if you really don't want the chgrp.

## Inspecting permissions

```bash
# Inside the container
ls -ldn /workspace
# drwxrwsr-x. 5 0 1000 ... /workspace
#                 ^ host_gid
```

```bash
# Outside, on the host
stat /path/to/your/project
```

## Common pitfalls

- **My project lives on a network drive that doesn't honour Unix groups.** Claudock's chgrp is a no-op there; fall back to `--no-update-fs` and adjust ACLs separately.
- **I want files created by root to be owned by my host user, not just my host group.** Out of scope: use `podman` with rootless or run the wrapper under your host UID.
- **A subprocess in the container ignores umask.** Some tools force their own mode (e.g. `git clone` uses `0755`). Set `umask 002` in the relevant tool's config or `chmod g+rwXs` after the fact.
