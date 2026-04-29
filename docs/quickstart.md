# Quickstart

This walks through one common path: start a named container on a project, run Claude Code inside it, stop it, restart it later.

## 1. Pull an image

```bash
claudock image install dev
```

## 2. Create a profile

```bash
claudock profile create personal
```

## 3. Start a container on a project

```bash
cd ~/code/my-project
claudock start my-project --cwd
```

This:

- Creates a container named `claudock-my-project`
- Mounts `~/code/my-project` at `/workspace`
- Mounts `~/.claudock/profiles/personal/.claude` at `/root/.claude`
- Drops you into a zsh shell
- Runs `claude` automatically when you exit the shell? No, you launch it yourself with `claude` once inside.

You should see the Claudock MOTD, then a custom 2-line prompt:

```
┌─[claudock]─(root@my-project)─[~/workspace]
└─# claude
```

## 4. Use Claude

Inside the container, run `claude`. The first invocation opens the OAuth login flow in your default browser (the URL is printed in the terminal). Tokens are written to `/root/.claude/`, which lives on the host at `~/.claudock/profiles/personal/.claude/`.

## 5. Detach and reuse

Exit the shell with `exit` or `Ctrl+D`. The container is **stopped** but not removed.

To re-attach later:

```bash
claudock start my-project          # reuses the existing container
```

State preserved: shell history, ad-hoc `apt install`s, `npm install`s, Claude conversations (under `/root/.claude/projects/`).

## 6. Inspect

```bash
claudock info               # list all Claudock containers
claudock logs my-project    # asciinema recordings (only if started with --log)
```

## 7. Clean up

```bash
claudock stop my-project
claudock remove my-project
```

## Common variations

- Throwaway container: `claudock start --tmp`
- Open VSCode in browser: `claudock start my-project --cwd --vscode` then visit `http://127.0.0.1:8080`
- Headed Chromium for Claude tools: `claudock start my-project --cwd --x11`
- Mount your SSH agent for git/SSH: `claudock start my-project --cwd --ssh`
- Clone a remote repo on creation: `claudock start my-fork --git git@github.com:you/repo.git`

See [flags.md](flags.md) for the complete list.
