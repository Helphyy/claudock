# Profiles: multi-profile Claude authentication

A **profile** is a directory under `~/.claudock/profiles/<name>/` that holds one set of Claude Code credentials. Every Claudock container bind-mounts one profile's `.claude/` directory to `/root/.claude/`, so the in-container `claude` CLI sees only that profile's tokens.

## Why profiles

- **Personal vs. work:** keep a `personal` OAuth login separate from a `work` API key.
- **Multiple subscriptions:** different Claude accounts, different rate limits.
- **Test isolation:** a `sandbox` profile that you can wipe whenever you want.

Two containers using the same profile share auth state. Two containers using different profiles are fully isolated.

## Layout

```
~/.claudock/profiles/
├── personal/
│   └── .claude/                    # bind-mounted to /root/.claude
│       ├── conversations/
│       ├── settings.json
│       └── ...
└── work/
    └── .claude/
```

## Commands

```bash
claudock profile list                 # show all profiles
claudock profile create personal      # mkdir + scaffold .claude/
claudock profile show personal        # presence of tokens, last access, size
claudock profile remove personal      # rm -rf, asks confirmation
```

## Picking a profile at start time

```bash
# Use the default profile (set in ~/.claudock/config.yml -> default_profile)
claudock start my-project --cwd

# Override per command
claudock start work-task --cwd --profile work

# Or set per project via .claudock.yml (see project-config.md)
# defaults:
#   profile: work
```

## First login

The very first time you run `claude` inside a container that uses a brand-new profile, Claude will prompt for OAuth or API key. The tokens land in `/root/.claude/`, which is your host `~/.claudock/profiles/<name>/.claude/`. Subsequent containers using the same profile are already authenticated.

## Pro tips

- Back up profiles: `tar czf claude-profiles.tar.gz -C ~/.claudock profiles`.
- Migrate: copy `~/.claudock/profiles/<name>/` to another machine, install Claudock, done.
- Profile permission: the host directory should be `0700`. Claudock sets that on `profile create`.
- Inspect profiles without entering a container: just `ls ~/.claudock/profiles/<name>/.claude/conversations/`.
