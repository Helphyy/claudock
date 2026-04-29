# Claudock documentation

User-facing documentation for the Claudock CLI (the Python wrapper).

## Index

1. [Installation](installation.md): install Claudock, configure Docker, log in to GHCR.
2. [Quickstart](quickstart.md): your first `claudock start`.
3. [Commands reference](commands.md): every verb and subcommand.
4. [Profiles](profiles.md): multi-profile Claude authentication.
5. [Images](images.md): the seven official variants and the `image` subcommand.
6. [Project config](project-config.md): per-project `.claudock.yml`.
7. [Start flags](flags.md): every flag you can pass to `claudock start`.
8. [Filesystem](filesystem.md): bind mounts, `host_gid`, `umask`, permissions.
9. [Networking](networking.md): bridge, host, none, port forwarding.
10. [Troubleshooting](troubleshooting.md): common pitfalls and fixes.

## Project layout

```
~/.claudock/
├── config.yml              # global config (default profile, image, registry, ...)
├── profiles/
│   └── <name>/
│       └── .claude/         # bind-mounted to /root/.claude in the container
└── logs/
    └── <container>/         # asciinema recordings when --log is used
```

## Where to ask questions

GitHub issues: <https://github.com/Helphyy/claudock/issues>
