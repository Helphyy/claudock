"""Business logic for claudock verbs (start, stop, info, profile...)."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from claudock.config import UserConfig, cache, find_project_config, load_config, load_project_config
from claudock.console import (
    console,
    container_table,
    log,
    print_container_recap,
    profile_table,
    progress,
    prompt,
    selector,
    status,
)
from claudock.console.errors import success_panel, warn_panel
from claudock.console.styles import status_markup, truncate_path
from claudock.constants import (
    CONFIG_FILE,
    CONTAINER_CLAUDE_DIR,
    CONTAINER_CLAUDE_JSON,
    CONTAINER_LOG_DIR,
    LOGS_DIR,
)
from claudock.exceptions import ContainerNotFoundError
from claudock.model import ClaudockContainer, ContainerConfig
from claudock.model.container_config import PortMapping, VolumeMount
from claudock.model.profile import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    create_profile,
    get_or_create_profile,
    get_profile,
    list_profiles,
    remove_profile,
)
from claudock.utils.docker_client import get_client

# Sentinels for "+ create new" entries in interactive selectors.
_NEW_CONTAINER = object()
_NEW_PROFILE = object()
_NEW_CONV = object()
_SHELL_ACTION = object()
_CONTAINER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


@dataclass
class StartOptions:
    """Extra options for `claudock start`.

    Scalar fields default to None ("not specified"), letting `cmd_start`
    fall back to the user/project config.
    """

    path: str | None = None
    use_cwd: bool = False
    image: str | None = None
    shell: str | None = None
    network: str | None = None
    hostname: str | None = None
    profile: str | None = None
    env: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)
    tmp: bool = False
    yes: bool = False
    log: bool = False
    x11: bool = False
    clipboard: bool = False
    no_update_fs: bool = False
    vscode: bool = False
    vscode_port: int = 8080
    git: str | None = None
    ssh: bool | str = False  # False=off, True=~/.ssh, str=custom path
    docker: bool = False  # mount /var/run/docker.sock (DooD, gives root on host)
    # Pass-through Claude Code flags (applied to the `claude` invocation on attach)
    dangerously_skip_permissions: bool = False
    continue_last: bool = False
    resume_id: str | None = None
    model: str | None = None
    permission_mode: str | None = None
    print_prompt: str | None = None
    add_dirs: list[str] = field(default_factory=list)
    ide: bool = False
    effort: str | None = None


def _resolve_workspace(opts: StartOptions, name: str, cfg: UserConfig) -> Path:
    if opts.use_cwd:
        return Path.cwd().resolve()
    if opts.path:
        return Path(opts.path).expanduser().resolve()
    return cfg.volumes.workspaces_path / name


_SENSITIVE_HOST_PREFIXES = (
    "/etc",
    "/root",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/var/run",
)


def _resolve_volume_host(spec: str) -> str:
    """Normalize the host side of a `host:container[:mode]` volume spec
    so `..`-style traversal surfaces as an absolute path. The spec keeps
    its container path and mode untouched."""
    parts = spec.split(":")
    if len(parts) < 2:
        return spec  # let VolumeMount.parse raise a clean error later
    parts[0] = str(Path(parts[0]).expanduser().resolve())
    return ":".join(parts)


def _warn_sensitive_mounts(specs: list[str]) -> None:
    """Print a warn line when a user volume points to a known-sensitive
    host directory (etc, root, proc, sys, dev, boot, var/run). The mount
    still proceeds; this is a heads-up, not a refusal."""
    for spec in specs:
        host = spec.split(":", 1)[0]
        for prefix in _SENSITIVE_HOST_PREFIXES:
            if host == prefix or host.startswith(prefix + "/"):
                log.warn(
                    f"Mounting host path [path]{host}[/] inside the container, "
                    "this exposes sensitive files. Make sure you trust the workload."
                )
                break


def _parse_env(items: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid env '{item}', expected KEY=VALUE")
        k, v = item.split("=", 1)
        env[k] = v
    return env


def _apply_project_config(opts: StartOptions, workspace_host: Path) -> StartOptions:
    """Apply a .claudock.yml from the workspace. CLI flags always win."""
    pc_path = find_project_config(workspace_host)
    if pc_path is None:
        return opts
    pc = load_project_config(pc_path)
    if pc is None:
        return opts
    log.info(f"Project config detected: [path]{pc_path}[/]")

    if opts.image is None and pc.image:
        opts.image = pc.image
    if opts.profile is None and pc.profile:
        opts.profile = pc.profile
    if opts.network is None and pc.network:
        opts.network = pc.network
    if opts.shell is None and pc.shell:
        opts.shell = pc.shell
    if opts.hostname is None and pc.hostname:
        opts.hostname = pc.hostname
    if not opts.log and pc.log:
        opts.log = bool(pc.log)
    if not opts.x11 and pc.x11:
        opts.x11 = bool(pc.x11)
    if not opts.clipboard and pc.clipboard:
        opts.clipboard = bool(pc.clipboard)
    if not opts.vscode and pc.vscode:
        opts.vscode = bool(pc.vscode)
    if opts.git is None and pc.git:
        opts.git = pc.git
    if not opts.ssh and pc.ssh:
        opts.ssh = bool(pc.ssh) if isinstance(pc.ssh, bool) else pc.ssh
    if not opts.docker and pc.docker:
        opts.docker = bool(pc.docker)
    # Lists/dicts: additive (project enriches CLI flags)
    if pc.caps:
        opts.caps = [*opts.caps, *pc.caps]
    if pc.env:
        existing_keys = {e.split("=", 1)[0] for e in opts.env if "=" in e}
        for k, v in pc.env.items():
            if k not in existing_keys:
                opts.env.append(f"{k}={v}")
    if pc.volumes:
        opts.volumes = [*opts.volumes, *pc.volumes]
    if pc.ports:
        opts.ports = [*opts.ports, *pc.ports]
    if opts.effort is None and pc.effort:
        opts.effort = pc.effort
    return opts


def _build_spec(name: str, opts: StartOptions, cfg: UserConfig) -> ContainerConfig:
    # Apply project .claudock.yml if present
    workspace_host_for_pc = _resolve_workspace(opts, name, cfg)
    opts = _apply_project_config(opts, workspace_host_for_pc)
    if opts.effort is None:
        opts.effort = cfg.config.default_effort
    if not opts.clipboard and cfg.config.default_clipboard:
        opts.clipboard = True

    profile = get_or_create_profile(opts.profile or cfg.config.default_profile)
    # Merge config defaults with CLI overrides; CLI wins on env conflicts.
    merged_env: dict[str, str] = {**cfg.config.default_env, **_parse_env(opts.env)}
    merged_caps: list[str] = []
    seen: set[str] = set()
    for c in [*cfg.config.default_caps, *opts.caps]:
        cap = c.upper()
        if cap not in seen:
            merged_caps.append(cap)
            seen.add(cap)
    logs_host = LOGS_DIR / name
    logs_host.mkdir(parents=True, exist_ok=True)

    # User-provided volumes: resolve the host part so a `-v ../../etc:/c:ro`
    # surfaces as `/etc:/c:ro` and the user sees what they are actually
    # mounting. Internal mounts added below (X11, docker.sock, ssh) are
    # already constructed with absolute paths.
    extra_volumes_specs = [_resolve_volume_host(v) for v in opts.volumes]
    _warn_sensitive_mounts(extra_volumes_specs)

    # X11 forwarding: mount the socket + forward DISPLAY + (optional) xauth.
    if opts.x11:
        extra_volumes_specs.append("/tmp/.X11-unix:/tmp/.X11-unix:rw")
        display = os.environ.get("DISPLAY")
        if display:
            merged_env.setdefault("DISPLAY", display)
        xauth = os.environ.get("XAUTHORITY")
        if xauth and Path(xauth).exists():
            extra_volumes_specs.append(f"{xauth}:/root/.Xauthority:ro")
            merged_env.setdefault("XAUTHORITY", "/root/.Xauthority")

    # Clipboard sharing (host → container). Lets Claude Code receive pasted
    # images/text from the host. Wayland: bind the compositor socket. X11:
    # piggy-back on the X11 path (which on its own doesn't carry clipboard
    # without a tool like xclip/xsel; we still mount what's needed).
    if opts.clipboard:
        wl_display = os.environ.get("WAYLAND_DISPLAY")
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
        wayland_ok = False
        if wl_display and xdg_runtime:
            sock = Path(xdg_runtime) / wl_display
            if sock.exists():
                # Mount the socket inside the container's runtime dir; root
                # inside the container uses uid 0, so /run/user/0 fits.
                extra_volumes_specs.append(f"{sock}:/run/user/0/{wl_display}:rw")
                merged_env.setdefault("WAYLAND_DISPLAY", wl_display)
                merged_env.setdefault("XDG_RUNTIME_DIR", "/run/user/0")
                wayland_ok = True
        if not wayland_ok:
            # Fall back to X11. Avoid duplicating the X11 socket spec if --x11
            # was also passed.
            x11_spec = "/tmp/.X11-unix:/tmp/.X11-unix:rw"
            if x11_spec not in extra_volumes_specs:
                extra_volumes_specs.append(x11_spec)
            display = os.environ.get("DISPLAY")
            if display:
                merged_env.setdefault("DISPLAY", display)
            xauth = os.environ.get("XAUTHORITY")
            if xauth and Path(xauth).exists():
                xauth_spec = f"{xauth}:/root/.Xauthority:ro"
                if xauth_spec not in extra_volumes_specs:
                    extra_volumes_specs.append(xauth_spec)
                merged_env.setdefault("XAUTHORITY", "/root/.Xauthority")

    # code-server: localhost-only port mapping at creation time.
    extra_ports_specs = list(opts.ports)
    if opts.vscode:
        extra_ports_specs.append(f"127.0.0.1:{opts.vscode_port}:8080")

    # Docker-out-of-Docker: bind the host Docker socket inside the container.
    if opts.docker:
        extra_volumes_specs.append("/var/run/docker.sock:/var/run/docker.sock:rw")
        # Optional: forward the user's docker config (registry creds, contexts).
        docker_cfg = Path.home() / ".docker" / "config.json"
        if docker_cfg.exists():
            extra_volumes_specs.append(f"{docker_cfg}:/root/.docker/config.json:ro")

    # SSH / git credentials forwarding (auto-enabled when --git is set).
    if opts.ssh or opts.git:
        home = Path.home()
        if isinstance(opts.ssh, str) and opts.ssh:
            ssh_dir = Path(opts.ssh).expanduser().resolve()
        else:
            ssh_dir = home / ".ssh"
        if ssh_dir.exists():
            extra_volumes_specs.append(f"{ssh_dir}:/root/.ssh:ro")
        else:
            log.warn(f"--ssh: directory {ssh_dir} not found, skipped")
        gitconfig = home / ".gitconfig"
        if gitconfig.exists():
            extra_volumes_specs.append(f"{gitconfig}:/root/.gitconfig:ro")
        git_creds = home / ".git-credentials"
        if git_creds.exists():
            extra_volumes_specs.append(f"{git_creds}:/root/.git-credentials:ro")
        ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
        if ssh_auth_sock and Path(ssh_auth_sock).exists():
            extra_volumes_specs.append(f"{ssh_auth_sock}:/ssh-agent:rw")
            merged_env["SSH_AUTH_SOCK"] = "/ssh-agent"

    return ContainerConfig(
        name=name,
        image=cfg.images.expand(opts.image or cfg.config.default_image),
        workspace_host=workspace_host_for_pc,
        profile_name=profile.name,
        profile_claude_dir=profile.claude_dir,
        profile_claude_json=profile.claude_json,
        logs_host_dir=logs_host,
        network_mode=opts.network or cfg.network.mode,
        hostname=opts.hostname,
        extra_env=merged_env,
        extra_volumes=[VolumeMount.parse(v) for v in extra_volumes_specs],
        extra_ports=[PortMapping.parse(p) for p in extra_ports_specs],
        extra_caps=merged_caps,
        disposable=opts.tmp,
    )


def cmd_start(name: str | None, opts: StartOptions) -> int:
    cfg = load_config()
    interactive_mode = name is None

    if interactive_mode:
        resolved = _interactive_resolve_start_name()
        if resolved is None:
            log.cancelled()
            return 1
        name = resolved

    entrypoint_cmd = _resolve_entrypoint(opts, cfg)

    if opts.tmp:
        return _run_disposable(name, opts, cfg, entrypoint_cmd)

    try:
        container = ClaudockContainer.get(name)
        log.info(
            f"Container '[name]{name}[/]' exists (profile [accent]{container.profile}[/])"
        )
        with status.step("Starting container..."):
            container.start()
        # Claude writes session files as root with 0600; host (non-root) then
        # can't read them and the resume picker degrades to bare UUIDs. Relax
        # read perms so _extract_title can pick up the summary/first prompt.
        _relax_claude_session_perms(container)
        # Conversation menu (existing container, TTY, no --shell, no -y)
        entrypoint_cmd = _pick_existing_action(container, opts, cfg)
    except ContainerNotFoundError:
        import sys
        if sys.stdin.isatty() and not opts.yes:
            opts = _interactive_augment_opts(opts, cfg)
        if opts.x11:
            warn_panel(
                "X11 socket shared",
                "The host's X11 socket will be mounted into the container.\n"
                "An app inside can observe/inject events on your X server.\n"
                "Acceptable for personal dev; do not enable for untrusted code.",
            )
        if opts.clipboard:
            warn_panel(
                "Clipboard shared with host",
                "The host's Wayland (or X11 fallback) socket will be exposed\n"
                "so Claude Code can receive pasted images/text from your host.\n"
                "The container needs 'wl-clipboard' (Wayland) or 'xclip'/'xsel'\n"
                "(X11) installed to actually read the clipboard.\n"
                "Anything inside can also inject input on your session, do not\n"
                "enable for untrusted code.",
            )
        if opts.docker:
            warn_panel(
                "Docker socket shared (DooD)",
                "/var/run/docker.sock is bind-mounted into the container.\n"
                "Anything inside (including Claude) gains effective root on your host\n"
                "(it can `docker run -v /:/host` and pwn everything).\n"
                "Use ONLY with code you fully trust.",
            )
        spec = _build_spec(name, opts, cfg)
        print_container_recap(spec)
        if not opts.yes and not prompt.confirm("Create this container now?", default=True):
            log.cancelled("Creation cancelled.")
            return 1
        spec.workspace_host.mkdir(parents=True, exist_ok=True)
        with status.step("Creating container..."):
            container = ClaudockContainer.create(spec)
        if not opts.no_update_fs:
            _update_workspace_perms(container)
        if opts.git:
            _git_clone_into_workspace(container, opts.git)
        if opts.vscode:
            warn_panel(
                "code-server enabled",
                "VSCode (FOSS, Open VSX) listens on 127.0.0.1:8080 with no auth.\n"
                "Reachable only from your localhost. Recreate the container to disable it.",
            )
            container.start_code_server()
        body = (
            f"Image: {spec.image}\n"
            f"Profile: {spec.profile_name}\n"
            f"Workspace: {spec.workspace_host}\n"
        )
        if opts.vscode:
            body += f"VSCode: http://127.0.0.1:{opts.vscode_port}\n"
        body += (
            f"\nRun a command without attaching: claudock exec {name} <cmd>\n"
            f"Stop: claudock stop {name}"
        )
        success_panel(f"Container '{name}' created", body)

    log_to = None
    if opts.log:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_to = f"{CONTAINER_LOG_DIR}/{ts}.cast"
        log.info(f"Session recorded at [path]~/.claudock/logs/{name}/{ts}.cast[/]")

    log.info(f"Launching: [value]{' '.join(entrypoint_cmd)}[/]")
    return container.attach_interactive(entrypoint_cmd, log_to=log_to)


def _git_clone_into_workspace(container: ClaudockContainer, url: str) -> None:
    """Clone the given git URL into /workspace. If empty → directly; else → subdir."""
    chk = container.raw.exec_run(["sh", "-c", "ls -A /workspace 2>/dev/null | head -1"])
    is_empty = chk.exit_code == 0 and not chk.output.strip()

    if is_empty:
        target = "/workspace"
    else:
        repo_name = url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        target = f"/workspace/{repo_name}"
        log.warn(f"/workspace not empty, cloning into {target}")

    log.info(f"git clone [value]{url}[/] → [path]{target}[/]")
    # exec_run with a list (no shell) defeats injection through `url`
    # (semicolons, backticks, $(...), etc.). stderr is folded into stdout
    # by docker SDK by default.
    res = container.raw.exec_run(
        ["git", "clone", "--recurse-submodules", url, target],
    )
    if res.exit_code == 0:
        log.success(f"Repo cloned into [path]{target}[/]")
    else:
        out = res.output.decode("utf-8", errors="replace")[:600]
        log.err(f"git clone failed:\n{out}")


def _relax_claude_session_perms(container: ClaudockContainer) -> None:
    """Make Claude's session JSONL files readable by the host user.

    Claude Code writes /root/.claude/projects/<cwd>/<id>.jsonl as root, mode
    0600. Since the profile is bind-mounted, those files are visible host-side
    but unreadable to a non-root user, so the resume picker can't extract the
    summary/first prompt and falls back to displaying the bare UUID. A
    one-shot `chmod -R o+rX` on the projects/ dir fixes it for past and
    future sessions (Claude doesn't reset perms on rewrite)."""
    cmd = "chmod -R o+rX /root/.claude/projects 2>/dev/null; true"
    try:
        container.raw.exec_run(["sh", "-c", cmd])
    except Exception:
        pass


def _update_workspace_perms(container: ClaudockContainer) -> None:
    """Apply setgid + host-group on /workspace so files created by root inside
    the container are group-writable from the host. Combined with `umask 002`
    in the image, new files default to mode 0664.
    """
    host_gid = os.getgid()
    cmd = (
        f"chgrp {host_gid} /workspace 2>/dev/null; "
        f"chmod g+rwXs /workspace 2>/dev/null; "
        "true"
    )
    try:
        container.raw.exec_run(["sh", "-c", cmd])
    except Exception:
        pass


def _resolve_entrypoint(opts: StartOptions, cfg: UserConfig) -> list[str]:
    """Pick the command launched on attach.

    - Default: `claude` (boots Claude Code directly).
    - If `opts.shell` (e.g. bash, zsh, tmux): that shell as a login shell.
    - Otherwise build the `claude` command with any pass-through flags.
    """
    if opts.shell:
        return [opts.shell, "-l"]
    return _build_claude_cmd(opts)


def _build_claude_cmd(opts: StartOptions, base: list[str] | None = None) -> list[str]:
    """Build a `claude` invocation, appending any pass-through flags from opts.

    `base` lets callers start from `["claude", "--resume", id]` etc. and still
    pick up `--model`, `--permission-mode`, `--print`, `--add-dir`, `--ide`,
    `--dangerously-skip-permissions`.
    """
    cmd = list(base) if base else ["claude"]
    if opts.continue_last and "--resume" not in cmd and "-c" not in cmd:
        cmd.append("--continue")
    if opts.resume_id and "--resume" not in cmd:
        cmd.extend(["--resume", opts.resume_id])
    if opts.model:
        cmd.extend(["--model", opts.model])
    if opts.permission_mode:
        cmd.extend(["--permission-mode", opts.permission_mode])
    if opts.dangerously_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if opts.effort:
        cmd.extend(["--effort", opts.effort])
    # Resolve --add-dir host paths so traversal surfaces explicitly.
    for d in (str(Path(d).expanduser().resolve()) for d in opts.add_dirs):
        cmd.extend(["--add-dir", d])
    if opts.ide:
        cmd.append("--ide")
    if opts.print_prompt is not None:
        cmd.extend(["--print", opts.print_prompt])
    return cmd


def _pick_existing_action(container: ClaudockContainer, opts: StartOptions, cfg: UserConfig) -> list[str]:
    """For an existing container: menu Claude conversation / new / shell.

    If non-TTY or opts.shell is set, short-circuit and return the default.
    """
    import sys
    if (
        opts.shell
        or opts.yes
        or not sys.stdin.isatty()
        or opts.continue_last
        or opts.resume_id
        or opts.print_prompt is not None
    ):
        return _resolve_entrypoint(opts, cfg)

    from claudock.utils.claude_sessions import fmt_relative, list_sessions

    try:
        profile = get_profile(container.profile)
    except Exception:
        return _resolve_entrypoint(opts, cfg)

    sessions = list_sessions(profile.claude_dir, "/workspace")
    items: list = [_NEW_CONV, *sessions, _SHELL_ACTION]
    shell_label = cfg.config.default_shell

    def _render(item: object) -> list[str]:
        if item is _NEW_CONV:
            return ["[ok]+ New Claude conversation[/]", ""]
        if item is _SHELL_ACTION:
            return [f"[accent]» Shell ({shell_label})[/]", ""]
        # ClaudeSession
        return [
            f"[name]{item.title}[/]",
            f"[muted]{fmt_relative(item.mtime_dt)}[/]",
        ]

    chosen = selector.select_from_table(
        items,
        title=f"Action on '[name]{container.name}[/]'",
        columns=["Conversation", "Modified"],
        render_row=_render,
        object_label="action",
        auto_single=False,
    )
    if chosen is None or chosen is _NEW_CONV:
        return _build_claude_cmd(opts)
    if chosen is _SHELL_ACTION:
        return [shell_label, "-l"]
    return _build_claude_cmd(opts, base=["claude", "--resume", chosen.id])


def _interactive_resolve_start_name() -> str | None:
    """Exegol-style flow: if existing containers, show selector + 'create new'
    option; otherwise prompt directly for a new name."""
    candidates = ClaudockContainer.list_all()

    if not candidates:
        log.info("No existing containers. Creating a new one.")
        return _ask_new_container_name()

    log.info(f"{len(candidates)} existing container(s):")
    items: list = [*candidates, _NEW_CONTAINER]

    def _render(item: object) -> list[str]:
        if item is _NEW_CONTAINER:
            return ["[ok]+ create new[/]", "", "", ""]
        c = item  # ClaudockContainer
        return [
            f"[name]{c.name}[/]",  # type: ignore[attr-defined]
            status_markup(c.status),  # type: ignore[attr-defined]
            f"[accent]{c.profile}[/]",  # type: ignore[attr-defined]
            c.image_tag,  # type: ignore[attr-defined]
        ]

    chosen = selector.select_from_table(
        items,
        title="Container to start (or create new)",
        columns=["Name", "Status", "Profile", "Image"],
        render_row=_render,
        object_label="container",
        auto_single=False,
    )
    if chosen is None:
        return None
    if chosen is _NEW_CONTAINER:
        return _ask_new_container_name()
    return chosen.name


def _interactive_augment_opts(opts: StartOptions, cfg: UserConfig) -> StartOptions:
    """Prompt for the main options of a brand-new container.

    Skip what was already passed via flag. When the user just presses Enter,
    fall back on the global config defaults.
    """
    # 0. Image (variant selector reused from `claudock image install`)
    if opts.image is None:
        chosen = _pick_variant_interactive(cfg, allow_all=False)
        if chosen:
            opts.image = chosen

    # 1. Workspace
    if not opts.use_cwd and not opts.path:
        choice = prompt.ask(
            "Workspace: 'c' = current dir, 'd' = default (~/.claudock/workspaces/<name>), 'p' = custom path",
            choices=["c", "d", "p"],
            default="d",
            show_choices=False,
        )
        if choice == "c":
            opts.use_cwd = True
        elif choice == "p":
            try:
                path = prompt.ask("Workspace path")
                if path:
                    opts.path = path
            except RuntimeError:
                pass

    # 2. Profile
    if opts.profile is None:
        profiles = list_profiles()
        if profiles:
            items: list = [*profiles, _NEW_PROFILE]
            chosen = selector.select_from_table(
                items,
                title="Claude auth profile",
                columns=["Name", "Size"],
                render_row=lambda p: (
                    ["[ok]+ create new profile[/]", ""]
                    if p is _NEW_PROFILE
                    else [
                        f"[name]{p.name}[/]",
                        f"[value]{_fmt_size_local(p.size_bytes)}[/]",
                    ]
                ),
                object_label="profile",
                auto_single=False,
            )
            if chosen is _NEW_PROFILE:
                try:
                    new_name = prompt.ask("New profile name", default="")
                except RuntimeError:
                    new_name = ""
                if new_name:
                    opts.profile = new_name
            elif chosen is not None:
                opts.profile = chosen.name

    # 3. Network
    if not opts.network:
        opts.network = prompt.ask(
            "Network",
            choices=["bridge", "host", "none"],
            default=cfg.network.mode,
        )

    # 4. Entrypoint: Claude direct, or a zsh shell?
    if opts.shell is None:
        choice = prompt.ask(
            "Entrypoint: 'c' = Claude (default), 's' = zsh shell",
            choices=["c", "s"],
            default="c",
            show_choices=False,
        )
        if choice == "s":
            opts.shell = "zsh"

    # 5. Logging
    if not opts.log:
        opts.log = prompt.confirm(
            "Record session (asciinema)?",
            default=False,
        )

    return opts


def _ask_new_container_name() -> str | None:
    """Prompt for a new container name with validation."""
    while True:
        try:
            name = prompt.ask("New container name", default="")
        except RuntimeError:
            return None
        if not name:
            return None
        if not _CONTAINER_NAME_RE.match(name):
            log.err("Invalid name. Expected: a-z, 0-9, '-', '_', max 32 chars, alphanumeric first character.")
            continue
        try:
            ClaudockContainer.get(name)
            log.err(f"Container '{name}' already exists. Pick another name.")
            continue
        except ContainerNotFoundError:
            return name


def _run_disposable(name: str, opts: StartOptions, cfg: UserConfig, entrypoint_cmd: list[str]) -> int:
    """`--tmp` mode: throwaway container, attached directly, removed on exit."""
    spec = _build_spec(name, opts, cfg)
    spec.workspace_host.mkdir(parents=True, exist_ok=True)
    spec.logs_host_dir.mkdir(parents=True, exist_ok=True)
    print_container_recap(spec)
    if not opts.yes and not prompt.confirm("Launch this disposable container?", default=True):
        log.cancelled()
        return 1
    log.info(f"Disposable container '[name]{name}[/]', removed on exit.")

    cmd = [
        "docker", "run", "--rm", "-it",
        "--name", spec.container_name,
        "--hostname", spec.hostname or spec.name,
        "--workdir", "/workspace",
        "--network", spec.network_mode,
        "--security-opt", "no-new-privileges:true",
        "-v", f"{spec.workspace_host}:/workspace:rw",
        "-v", f"{spec.profile_claude_dir}:{CONTAINER_CLAUDE_DIR}:rw",
        "-v", f"{spec.profile_claude_json}:{CONTAINER_CLAUDE_JSON}:rw",
        "-v", f"{spec.logs_host_dir}:{CONTAINER_LOG_DIR}:rw",
    ]
    for v in spec.extra_volumes:
        cmd += ["-v", f"{v.host}:{v.container}:{v.mode}"]
    for p in spec.extra_ports:
        cmd += ["-p", f"{p.host}:{p.container}/{p.proto}"]
    for c in spec.extra_caps:
        cmd += ["--cap-add", c]
    for k, v in _parse_env(opts.env).items():
        cmd += ["-e", f"{k}={v}"]
    cmd += ["-e", "TERM=xterm-256color", "-e", "LANG=C.UTF-8"]
    for k, v in spec.labels.items():
        cmd += ["--label", f"{k}={v}"]
    cmd += [spec.image, *entrypoint_cmd]
    return subprocess.call(cmd, env=os.environ.copy())


def cmd_stop(name: str | None) -> int:
    target = _resolve_one(name, running_only=True, action="stop")
    if target is None:
        return 1
    with status.step(f"Stopping '{target.name}'..."):
        target.stop()
    log.success(f"Container '[name]{target.name}[/]' stopped.")
    return 0


def cmd_restart(name: str | None) -> int:
    target = _resolve_one(name, running_only=False, action="restart")
    if target is None:
        return 1
    with status.step(f"Restarting '{target.name}'..."):
        target.raw.restart()
        target.reload()
    log.success(f"Container '[name]{target.name}[/]' restarted.")
    return 0


def cmd_remove(name: str | None, force: bool) -> int:
    target = _resolve_one(name, running_only=False, action="remove")
    if target is None:
        return 1

    if not force:
        warn_panel(
            f"Removing '{target.name}'",
            f"Status: {target.status}\n"
            f"Profile: {target.profile} (kept)\n"
            f"Workspace: {target.workspace} (kept on host)\n\n"
            "The container, its installed packages and its shell history will be deleted.",
        )
        if not prompt.confirm(f"Permanently remove container '{target.name}'?", default=False):
            log.cancelled("Removal cancelled.")
            return 0

    with status.step(f"Removing '{target.name}'..."):
        target.remove(force=force or target.status == "running")
    log.success(f"Container '[name]{target.name}[/]' removed.")
    return 0


def cmd_exec(name: str, command: list[str]) -> int:
    container = ClaudockContainer.get(name)
    if container.status != "running":
        container.start()
    return container.exec_command(command)


def cmd_logs(name: str | None) -> int:
    """List recorded sessions of a container."""
    target_name = name
    if target_name is None:
        target = _resolve_one(None, running_only=False, action="show logs for")
        if target is None:
            return 1
        target_name = target.name

    logs_dir = LOGS_DIR / target_name
    if not logs_dir.exists():
        log.info(f"No logs for '{target_name}'.")
        return 0

    casts = sorted(logs_dir.glob("*.cast"))
    if not casts:
        log.info(f"No recorded session for '{target_name}'.")
        log.info("Start with `claudock start <name> --log` to enable recording.")
        return 0

    from rich.table import Table
    from claudock.console.styles import TABLE_BOX, fmt_size
    table = Table(
        title=f"Recorded sessions of [name]{target_name}[/]",
        title_style="brand",
        header_style="bold cyan",
        border_style="brand.dim",
        box=TABLE_BOX,
        pad_edge=True,
    )
    table.add_column("File", style="value")
    table.add_column("Size", justify="right")
    table.add_column("Modified", style="muted")
    from datetime import datetime
    for c in casts:
        st = c.stat()
        table.add_row(
            c.name,
            fmt_size(st.st_size),
            datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)
    log.info(f"Folder: [path]{logs_dir}[/]")
    log.info("Replay: [kbd] asciinema play <file> [/]")
    return 0


def cmd_install(image: str | None) -> int:
    """Top-level shortcut for `claudock image install`."""
    return cmd_image_install(image)


def _split_repo_tag(image_ref: str) -> tuple[str, str]:
    """Split 'foo/bar:tag' into ('foo/bar', 'tag'). Defaults to ':latest'.

    Handles registry-with-port refs like `localhost:5000/foo/bar` (no tag)
    by checking that nothing after the last `:` contains a `/`."""
    if ":" not in image_ref:
        return image_ref, "latest"
    head, _, tail = image_ref.rpartition(":")
    if "/" in tail:
        # The colon was the registry port separator, not a tag boundary
        return image_ref, "latest"
    return head, tail


def _pick_variant_interactive(cfg: UserConfig, *, allow_all: bool = True) -> str | None:
    """Show a table of variants (optionally with an 'all' shortcut) and return
    the user's choice. Returns None when stdin is not a TTY (caller will fall
    back to default)."""
    import sys
    if not sys.stdin.isatty():
        return None

    from claudock.console.selector import select_from_table
    from claudock.console.styles import fmt_size
    from claudock.utils.image_updates import (
        check_updates,
        status_markup as update_status_markup,
    )

    client = get_client()
    local: dict[str, int] = {}
    for img in client.images.list():
        size = img.attrs.get("Size", 0)
        for t in (img.tags or []):
            local[t] = size

    items = ["all", *cfg.images.variants] if allow_all else list(cfg.images.variants)

    refs = [cfg.images.expand(v) for v in cfg.images.variants]
    updates = check_updates(client, refs)

    def render(item: str) -> list[str]:
        if item == "all":
            return [
                "all",
                "[muted]pull every variant[/]",
                "[muted]-[/]",
                "[muted]-[/]",
                "[muted]-[/]",
            ]
        full_ref = cfg.images.expand(item)
        size = local.get(full_ref)
        status = "[ok]✓ local[/]" if size is not None else "[muted]not local[/]"
        size_s = fmt_size(size) if size is not None else "[muted]-[/]"
        update = update_status_markup(updates.get(full_ref, "unknown"))
        return [item, full_ref, status, size_s, update]

    return select_from_table(
        items,
        title="Pick an image to install",
        columns=["Variant", "Reference", "Status", "Size", "Update"],
        render_row=render,
        object_label="image",
        auto_single=False,
    )


def cmd_image_install(image: str | None) -> int:
    """Pull an image from the registry. Accepts a known variant name
    (e.g. `dev`), a `claudock-<variant>` shortname, or a full image ref.
    Without an argument, an interactive selector lists every variant plus
    an `all` shortcut; non-TTY callers fall back to `config.default_image`."""
    cfg = load_config()
    if image is None:
        choice = _pick_variant_interactive(cfg)
        if choice is None:
            raw = cfg.config.default_image
        elif choice == "all":
            return cmd_image_install_all()
        else:
            raw = choice
    else:
        raw = image
    target = cfg.images.expand(raw)
    repo, tag = _split_repo_tag(target)

    client = get_client()
    if progress.pull_image(client, repo, tag):
        try:
            img = client.images.get(f"{repo}:{tag}")
            cache.record_image(f"{repo}:{tag}", size=img.attrs.get("Size", 0))
        except Exception:
            pass
        log.success(f"Image [value]{repo}:{tag}[/] ready.")
        return 0
    log.err(f"Pull of {repo}:{tag} failed.")
    return 1


def cmd_image_install_all() -> int:
    """Pull every official variant declared in the config."""
    cfg = load_config()
    if not cfg.images.variants:
        log.info("No variants declared in config.images.variants.")
        return 0
    log.info(f"Pulling {len(cfg.images.variants)} variants from [value]{cfg.images.registry or '(local)'}[/]...")
    failed: list[str] = []
    for v in cfg.images.variants:
        log.info(f"--- {v} ---")
        rc = cmd_image_install(v)
        if rc != 0:
            failed.append(v)
    if failed:
        log.err(f"Failed: {', '.join(failed)}")
        return 1
    log.success(f"All {len(cfg.images.variants)} variants pulled.")
    return 0


def cmd_image_update(image: str | None) -> int:
    """Re-pull an image from the registry to refresh its tag."""
    return cmd_image_install(image)


def cmd_image_remove(image: str, force: bool = False) -> int:
    """Remove a local Docker image (`docker rmi`). Accepts variant names too."""
    cfg = load_config()
    target = cfg.images.expand(image)
    client = get_client()
    # Accept the input as-is too (user may want to remove a non-prefixed tag)
    candidates = [target, image]
    seen = set()
    last_err: Exception | None = None
    for ref in candidates:
        if ref in seen:
            continue
        seen.add(ref)
        try:
            client.images.remove(ref, force=force)
            log.success(f"Image [value]{ref}[/] removed.")
            return 0
        except Exception as exc:
            last_err = exc
    log.err(f"Remove failed: {last_err}")
    return 1


def cmd_image_list() -> int:
    """Two tables:
    - Official variants (from config) with their pulled state + size + update status.
    - Other Claudock-tagged images present locally (custom builds).
    """
    from rich.table import Table
    from claudock.console.styles import TABLE_BOX, fmt_size
    from claudock.utils.image_updates import (
        check_updates,
        status_markup as update_status_markup,
    )

    cfg = load_config()
    client = get_client()
    images = client.images.list()

    # Collect all local tags + sizes
    local: dict[str, tuple[int, str]] = {}
    for img in images:
        size = img.attrs.get("Size", 0)
        sid = img.short_id
        for t in (img.tags or []):
            local[t] = (size, sid)

    # Pull update status for every official ref (cached 1h, parallel calls)
    official_refs_list = [cfg.images.expand(v) for v in cfg.images.variants]
    updates = check_updates(client, official_refs_list)

    # --- Official variants table ---
    table = Table(
        title="Official Claudock variants",
        title_style="brand",
        header_style="bold cyan",
        border_style="brand.dim",
        box=TABLE_BOX,
        pad_edge=True,
    )
    table.add_column("Variant", style="name")
    table.add_column("Local", justify="center")
    table.add_column("Tag", style="value")
    table.add_column("Size", justify="right")
    table.add_column("Update", justify="center")
    table.add_column("Reference", style="path", overflow="fold")
    for v in cfg.images.variants:
        full_ref = cfg.images.expand(v)
        # Match either the full registry ref or a shortname
        short_ref = f"claudock-{v}:{cfg.images.default_tag}"
        match = local.get(full_ref) or local.get(short_ref)
        # Also try `claudock-<v>:dev` (locally built)
        for cand_tag in ("dev", cfg.images.default_tag, "latest"):
            if match:
                break
            cand = f"claudock-{v}:{cand_tag}"
            match = local.get(cand)
            if match:
                short_ref = cand
        update_cell = update_status_markup(updates.get(full_ref, "unknown"))
        if match:
            size, _ = match
            table.add_row(
                v,
                "[ok]✓[/]",
                short_ref.split(":", 1)[1] if ":" in short_ref else "?",
                fmt_size(size),
                update_cell,
                full_ref,
            )
        else:
            table.add_row(v, "[muted]-[/]", "[muted]-[/]", "[muted]-[/]", update_cell, full_ref)
    console.print(table)

    # --- Other claudock-tagged images ---
    official_refs = set()
    for v in cfg.images.variants:
        official_refs.add(cfg.images.expand(v))
        for tag_variant in ("dev", cfg.images.default_tag, "latest"):
            official_refs.add(f"claudock-{v}:{tag_variant}")
    others: list[tuple[str, int, str]] = []
    for tag, (size, sid) in local.items():
        short = tag.rsplit("/", 1)[-1]
        if "claudock" in short and tag not in official_refs:
            others.append((tag, size, sid))

    if others:
        t2 = Table(
            title="Other local Claudock images",
            title_style="brand",
            header_style="bold cyan",
            border_style="brand.dim",
            box=TABLE_BOX,
            pad_edge=True,
        )
        t2.add_column("Tag", style="value")
        t2.add_column("Size", justify="right")
        t2.add_column("ID", style="muted")
        for tag, size, sid in sorted(others):
            t2.add_row(tag, fmt_size(size), sid)
        console.print(t2)

    log.info(
        f"Registry: [value]{cfg.images.registry or '(local-only)'}[/]"
        f"  ·  default tag: [value]{cfg.images.default_tag}[/]"
    )
    return 0


def cmd_image_build(path: str, name: str | None, tag: str = "dev") -> int:
    """Build a local Dockerfile and tag it as a Claudock image.

    `path` is the build context (folder containing the Dockerfile).
    `name` defaults to the basename of the path; final tag is `name:tag`.
    """
    build_path = Path(path).expanduser().resolve()
    if not build_path.is_dir():
        log.err(f"Build path '{build_path}' is not a directory.")
        return 2
    dockerfile = build_path / "Dockerfile"
    if not dockerfile.is_file():
        log.err(f"No Dockerfile found in '{build_path}'.")
        return 2
    image_name = name or build_path.name
    full_tag = f"{image_name}:{tag}"

    log.info(f"Building [value]{full_tag}[/] from [path]{build_path}[/]...")
    client = get_client()
    try:
        # Stream build output
        for chunk in client.api.build(
            path=str(build_path),
            tag=full_tag,
            rm=True,
            decode=True,
        ):
            if "stream" in chunk:
                line = chunk["stream"].rstrip()
                if line:
                    log.verbose(line)
            elif "error" in chunk:
                log.err(chunk["error"])
                return 1
        img = client.images.get(full_tag)
        cache.record_image(full_tag, size=img.attrs.get("Size", 0))
    except Exception as exc:
        log.err(f"Build failed: {exc}")
        return 1
    log.success(f"Image [value]{full_tag}[/] built.")
    return 0


def cmd_info() -> int:
    containers = ClaudockContainer.list_all()
    if not containers:
        log.info("No Claudock containers.")
        return 0
    console.print(container_table(containers))
    # Passive cache of seen images
    for c in containers:
        try:
            cache.record_image(c.image_tag)
        except Exception:
            pass
    return 0


# --- config verb -------------------------------------------------------------


def cmd_config_show() -> int:
    """Display the resolved configuration."""
    from claudock.console.errors import info_panel
    cfg = load_config()
    body_lines = [
        f"[key]File[/]: [path]{CONFIG_FILE}[/]",
        "",
        "[bold cyan]Volumes[/]",
        f"  workspaces_path  : [path]{cfg.volumes.workspaces_path}[/]",
        "",
        "[bold cyan]Config[/]",
        f"  default_image    : [value]{cfg.config.default_image}[/]",
        f"  default_profile  : [accent]{cfg.config.default_profile}[/]",
        f"  default_shell    : [value]{cfg.config.default_shell}[/]",
        f"  default_caps     : {', '.join(cfg.config.default_caps) or '[muted]none[/]'}",
        f"  default_env      : {_render_env(cfg.config.default_env)}",
        f"  auto_check_update: {cfg.config.auto_check_update}",
        "",
        "[bold cyan]Network[/]",
        f"  mode             : [value]{cfg.network.mode}[/]",
        "",
        "[bold cyan]UI[/]",
        f"  banner           : {cfg.ui.banner}",
    ]
    info_panel("Claudock configuration", "\n".join(body_lines))
    return 0


def _render_env(env: dict[str, str]) -> str:
    if not env:
        return "[muted]none[/]"
    return "\n  " + " " * 17 + ("\n  " + " " * 17).join(f"{k}=[value]{v}[/]" for k, v in env.items())


def cmd_config_path() -> int:
    console.print(str(CONFIG_FILE))
    return 0


def cmd_config_edit() -> int:
    import shutil
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        for cand in ("nano", "vim", "vi"):
            if shutil.which(cand):
                editor = cand
                break
    if not editor:
        log.err("No editor found. Set $EDITOR.")
        return 1
    # Force-create the config file if missing.
    load_config()
    return subprocess.call([editor, str(CONFIG_FILE)])


# --- profile verb ------------------------------------------------------------


def cmd_profile_list() -> int:
    profiles = list_profiles()
    containers = ClaudockContainer.list_all()
    counts: dict[str, int] = {}
    for c in containers:
        counts[c.profile] = counts.get(c.profile, 0) + 1

    if not profiles:
        log.info("No profiles. The 'default' profile will be created on first `claudock start`.")
        return 0

    console.print(profile_table(profiles, counts))
    return 0


def cmd_profile_create(name: str | None) -> int:
    if name is None:
        try:
            name = prompt.ask("New profile name", default="")
        except RuntimeError:
            log.err("Name required.")
            return 2
        if not name:
            log.cancelled()
            return 1
    p = create_profile(name)
    success_panel(
        f"Profile '{p.name}' created",
        f"Path: {p.claude_dir}\n"
        "Claude Code will prompt for login on first run of a container using this profile.",
    )
    return 0


def cmd_profile_remove(name: str | None, force: bool) -> int:
    resolved = _resolve_profile(name, action="remove")
    if resolved is None:
        return 1
    name = resolved
    p = get_profile(name)
    if not p.path.exists():
        log.err(f"No profile '{name}'.")
        return 1

    used_by = [c for c in ClaudockContainer.list_all() if c.profile == name]
    if used_by:
        names = ", ".join(c.name for c in used_by)
        warn_panel(
            f"Profile '{name}' in use",
            f"Linked containers: {names}\n"
            "These containers will keep referencing the path (which will be empty).",
        )

    if not force:
        from claudock.console.styles import fmt_size
        if not prompt.confirm(
            f"Permanently remove profile '{name}' ({fmt_size(p.size_bytes)})?",
            default=False,
        ):
            log.cancelled()
            return 0

    remove_profile(name)
    log.success(f"Profile '[name]{name}[/]' removed.")
    return 0


def cmd_profile_show(name: str | None) -> int:
    resolved = _resolve_profile(name, action="show")
    if resolved is None:
        return 1
    name = resolved
    p = get_profile(name)
    if not p.path.exists():
        log.err(f"No profile '{name}'.")
        return 1

    used_by = [c for c in ClaudockContainer.list_all() if c.profile == name]
    from claudock.console.styles import fmt_size
    body_lines = [
        f"Path        : {p.path}",
        f".claude/    : {p.claude_dir}",
        f"Size        : {fmt_size(p.size_bytes)}",
        f"Last mod    : {p.last_modified.strftime('%Y-%m-%d %H:%M') if p.last_modified else '-'}",
        f"Containers  : {len(used_by)}",
    ]
    for c in used_by:
        body_lines.append(f"  - {c.name} ({c.status})")

    from claudock.console.errors import info_panel
    info_panel(f"Profile {name}", "\n".join(body_lines))
    return 0


# --- helpers -----------------------------------------------------------------


def _fmt_size_local(n: int) -> str:
    from claudock.console.styles import fmt_size
    return fmt_size(n)


def _resolve_one(
    name: str | None,
    *,
    running_only: bool,
    action: str,
) -> ClaudockContainer | None:
    """Resolve the target container, by name or via interactive selector."""
    if name:
        try:
            return ClaudockContainer.get(name)
        except ContainerNotFoundError:
            log.err(f"No container named '{name}'.")
            return None

    candidates = ClaudockContainer.list_all()
    if running_only:
        candidates = [c for c in candidates if c.status == "running"]

    if not candidates:
        log.info(f"No container to {action}.")
        return None

    return selector.select_from_table(
        candidates,
        title=f"Container to {action}",
        columns=["Name", "Status", "Profile", "Image", "Workspace"],
        render_row=lambda c: [
            f"[name]{c.name}[/]",
            status_markup(c.status),
            f"[accent]{c.profile}[/]",
            c.image_tag,
            truncate_path(c.workspace, 40),
        ],
        object_label="container",
    )


def _resolve_profile(name: str | None, *, action: str) -> str | None:
    """Resolve a target profile, by name or via interactive selector."""
    profiles = list_profiles()
    if name:
        if not any(p.name == name for p in profiles):
            log.err(f"No profile '{name}'.")
            return None
        return name

    if not profiles:
        log.info(f"No profile to {action}.")
        return None

    chosen = selector.select_from_table(
        profiles,
        title=f"Profile to {action}",
        columns=["Name", "Size"],
        render_row=lambda p: [
            f"[name]{p.name}[/]",
            f"[value]{_fmt_size_local(p.size_bytes)}[/]",
        ],
        object_label="profile",
    )
    return chosen.name if chosen else None
