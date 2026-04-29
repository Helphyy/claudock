"""CLI entrypoint: parses args and dispatches to the manager."""

from __future__ import annotations

import argparse
import sys

from rich_argparse import RichHelpFormatter

from claudock import __version__
from claudock.console import log, show_exception

# Color the --help output via rich-argparse (palette aligned with our theme).
RichHelpFormatter.styles["argparse.prog"] = "bold bright_cyan"
RichHelpFormatter.styles["argparse.groups"] = "bold cyan"
RichHelpFormatter.styles["argparse.args"] = "bold magenta"
RichHelpFormatter.styles["argparse.metavar"] = "bright_white"
RichHelpFormatter.styles["argparse.help"] = "default"
RichHelpFormatter.styles["argparse.text"] = "default"
RichHelpFormatter.styles["argparse.syntax"] = "reverse bold cyan"
RichHelpFormatter.styles["argparse.default"] = "grey50"


class ColoredParser(argparse.ArgumentParser):
    """ArgumentParser that defaults to rich-argparse, propagated to subparsers."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("formatter_class", RichHelpFormatter)
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]


from claudock.manager import manager
from claudock.manager.manager import StartOptions


def _build_parser() -> argparse.ArgumentParser:
    parser = ColoredParser(
        prog="claudock",
        description="Secure containerized wrapper for Claude Code, with named persistent containers.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug output (implies --verbose)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm prompts")

    sub = parser.add_subparsers(
        dest="command", metavar="VERB", required=False, parser_class=ColoredParser,
    )

    sub.add_parser("version", help="Print the claudock version")

    p_start = sub.add_parser(
        "start",
        help="Create / start / attach a named container. Without a name: interactive flow.",
    )
    p_start.add_argument(
        "name", nargs="?",
        help="Container name. Empty: selector of existing ones plus 'create new'.",
    )
    p_start.add_argument("path", nargs="?", help="Host workdir to mount at /workspace")
    p_start.add_argument("--cwd", action="store_true", help="Use the current cwd as /workspace")
    p_start.add_argument("--image", help="Override the default image")
    p_start.add_argument("-s", "--shell", help="Shell to launch instead of claude (bash, zsh)")
    p_start.add_argument("--network", help="Docker network mode (bridge, host, none, <name>)")
    p_start.add_argument("--hostname", help="Container hostname (default: container name)")
    p_start.add_argument(
        "--profile", default=None,
        help="Claude auth profile (default: config.default_profile)",
    )
    p_start.add_argument(
        "-e", "--env", action="append", default=[], metavar="KEY=VAL",
        help="Environment variable to inject (repeatable)",
    )
    p_start.add_argument(
        "-V", "--volume", action="append", default=[], dest="volumes", metavar="HOST:CONT[:MODE]",
        help="Extra bind mount (repeatable)",
    )
    p_start.add_argument(
        "-p", "--port", action="append", default=[], dest="ports", metavar="HOST:CONT[/PROTO]",
        help="Port to expose (repeatable)",
    )
    p_start.add_argument(
        "--cap", action="append", default=[], dest="caps", metavar="CAP_NAME",
        help="Linux capability to add (repeatable, e.g. SYS_PTRACE)",
    )
    p_start.add_argument("--tmp", action="store_true", help="Disposable container, removed on exit")
    p_start.add_argument("--log", action="store_true", help="Record the shell session (asciinema)")
    p_start.add_argument(
        "--x11", action="store_true",
        help="Share the host X server (GUI apps inside the container, e.g. headed browsers)",
    )
    p_start.add_argument(
        "--no-update-fs", action="store_true", dest="no_update_fs",
        help="Skip the chgrp/setgid on /workspace (default: enabled so the host user can rw new files)",
    )
    p_start.add_argument(
        "--vscode", action="store_true",
        help="Start code-server (FOSS VSCode) on attach. Default port 127.0.0.1:8080.",
    )
    p_start.add_argument(
        "--vscode-port", type=int, default=8080, dest="vscode_port",
        help="Host port for code-server (default: 8080)",
    )
    p_start.add_argument(
        "-g", "--git", metavar="URL",
        help="Clone a git URL into /workspace after creation (auto-enables --ssh)",
    )
    p_start.add_argument(
        "--ssh", nargs="?", const=True, default=False, metavar="DIR",
        help="Forward an SSH directory (default: ~/.ssh, or a custom path) + ~/.gitconfig + SSH_AUTH_SOCK",
    )
    p_start.add_argument(
        "--docker", action="store_true",
        help="Mount the host Docker socket (DooD). DANGEROUS: gives effective root on the host. Only use on trusted code.",
    )
    p_start.add_argument(
        "--dangerously-skip-permissions", action="store_true",
        dest="dangerously_skip_permissions",
        help="Pass --dangerously-skip-permissions to Claude Code on launch (no per-tool prompts). Only safe inside the container's isolated /workspace.",
    )
    p_start.add_argument(
        "-c", "--continue", action="store_true", dest="continue_last",
        help="Continue Claude's most recent conversation on launch (skips the picker).",
    )
    p_start.add_argument(
        "-r", "--resume", metavar="ID", dest="resume_id",
        help="Resume a specific Claude conversation by session ID.",
    )
    p_start.add_argument(
        "--model", metavar="NAME",
        help="Pick the Claude model (e.g. claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5).",
    )
    p_start.add_argument(
        "--permission-mode", dest="permission_mode",
        choices=["default", "acceptEdits", "plan", "bypassPermissions"],
        help="Pass --permission-mode to Claude Code (alternative to --dangerously-skip-permissions).",
    )
    p_start.add_argument(
        "--print", metavar="PROMPT", dest="print_prompt",
        help="Non-interactive: run Claude with the given prompt and exit. Makes claudock usable in CI/scripts.",
    )
    p_start.add_argument(
        "--add-dir", action="append", default=[], dest="add_dirs", metavar="PATH",
        help="Extra directory Claude can read from (in addition to /workspace). Repeatable.",
    )
    p_start.add_argument(
        "--ide", action="store_true",
        help="Tell Claude to connect to the IDE (paired with --vscode for code-server integration).",
    )

    p_stop = sub.add_parser("stop", help="Stop a container (selector if no name)")
    p_stop.add_argument("name", nargs="?")

    p_restart = sub.add_parser("restart", help="Restart a container")
    p_restart.add_argument("name", nargs="?")

    sub.add_parser("exec", help="Run a command: claudock exec <name> <cmd...>")

    p_remove = sub.add_parser("remove", help="Remove a container")
    p_remove.add_argument("name", nargs="?")
    p_remove.add_argument("-f", "--force", action="store_true", help="Force removal without confirm")

    sub.add_parser("info", help="List Claudock containers")

    p_install = sub.add_parser("install", help="Pull a Docker image from the registry (alias of `image install`)")
    p_install.add_argument("image", nargs="?", help="Image to pull (default: config image)")

    p_image = sub.add_parser("image", help="Image management (list/install/update/remove/build)")
    p_image_sub = p_image.add_subparsers(
        dest="image_action", metavar="ACTION", required=True, parser_class=ColoredParser,
    )
    p_image_sub.add_parser("list", help="List Claudock images (official variants + local custom)")
    p_img_install = p_image_sub.add_parser(
        "install",
        help="Pull a variant by name (minimal/dev/cloud/security/full) or a full image ref",
    )
    p_img_install.add_argument("image", nargs="?", help="Variant name or image ref (default: config image)")
    p_image_sub.add_parser("install-all", help="Pull every official variant from the registry")
    p_img_update = p_image_sub.add_parser("update", help="Re-pull an image to refresh its tag")
    p_img_update.add_argument("image", nargs="?", help="Variant name or image ref (default: config image)")
    p_img_remove = p_image_sub.add_parser("remove", help="Remove a local image (`docker rmi`)")
    p_img_remove.add_argument("image", help="Variant name or image ref")
    p_img_remove.add_argument("-f", "--force", action="store_true", help="Force removal")
    p_img_build = p_image_sub.add_parser("build", help="Build a local Dockerfile and tag it as a Claudock image")
    p_img_build.add_argument("path", help="Build context (folder containing the Dockerfile)")
    p_img_build.add_argument("--name", help="Image name (default: basename of path)")
    p_img_build.add_argument("--tag", default="dev", help="Tag suffix (default: dev)")

    p_logs = sub.add_parser("logs", help="List recorded sessions of a container")
    p_logs.add_argument("name", nargs="?")

    p_config = sub.add_parser("config", help="User config management")
    p_config_sub = p_config.add_subparsers(
        dest="config_action", metavar="ACTION", required=True, parser_class=ColoredParser,
    )
    p_config_sub.add_parser("show", help="Display the resolved config")
    p_config_sub.add_parser("path", help="Print the config file path")
    p_config_sub.add_parser("edit", help="Open the config in $EDITOR")

    p_profile = sub.add_parser("profile", help="Claude auth profile management")
    p_profile_sub = p_profile.add_subparsers(
        dest="profile_action", metavar="ACTION", required=True, parser_class=ColoredParser,
    )
    p_profile_sub.add_parser("list", help="List existing profiles")
    p_create = p_profile_sub.add_parser("create", help="Create a profile (prompt if no name)")
    p_create.add_argument("name", nargs="?")
    p_remove_pr = p_profile_sub.add_parser("remove", help="Remove a profile (selector if no name)")
    p_remove_pr.add_argument("name", nargs="?")
    p_remove_pr.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    p_show = p_profile_sub.add_parser("show", help="Show profile details (selector if no name)")
    p_show.add_argument("name", nargs="?")

    return parser


def _print_dashboard() -> None:
    """Default render when `claudock` is called without a verb."""
    from claudock.console import console, print_banner
    from claudock.model import ClaudockContainer
    from claudock.model.profile import list_profiles

    print_banner()
    console.print()

    containers = ClaudockContainer.list_all()
    if containers:
        from claudock.console import container_table
        console.print(container_table(containers))
    else:
        console.print("[muted]No containers yet. Start your first project:[/]")
        console.print("  [kbd] claudock start my-project --cwd [/]\n")

    profiles = list_profiles()
    if profiles:
        counts: dict[str, int] = {}
        for c in containers:
            counts[c.profile] = counts.get(c.profile, 0) + 1
        from claudock.console import profile_table
        console.print(profile_table(profiles, counts))

    console.print()
    console.print("[hint]Main commands:[/]")
    console.print(
        "  [kbd] start [/]  [kbd] stop [/]  [kbd] restart [/]  "
        "[kbd] exec [/]  [kbd] info [/]  [kbd] remove [/]  [kbd] profile [/]"
    )
    console.print("[hint]Per-verb help:[/] claudock <verb> --help")


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    parser = _build_parser()

    if raw and raw[0] == "exec":
        if len(raw) < 3:
            log.err("Usage: claudock exec <name> <command...>")
            return 2
        name = raw[1]
        command = raw[2:]
        if command and command[0] == "--":
            command = command[1:]
        try:
            return manager.cmd_exec(name, command)
        except Exception as exc:
            show_exception(exc)
            return 1

    args = parser.parse_args(raw)

    log.set_verbosity(verbose=args.verbose, debug=args.debug, quiet=args.quiet)

    if args.command is None:
        _print_dashboard()
        return 0

    try:
        match args.command:
            case "start":
                opts = StartOptions(
                    path=args.path,
                    use_cwd=args.cwd,
                    image=args.image,
                    shell=args.shell,
                    network=args.network,
                    hostname=args.hostname,
                    profile=args.profile,
                    env=args.env,
                    volumes=args.volumes,
                    ports=args.ports,
                    caps=args.caps,
                    tmp=args.tmp,
                    yes=args.yes,
                    log=args.log,
                    x11=args.x11,
                    no_update_fs=args.no_update_fs,
                    vscode=args.vscode,
                    vscode_port=args.vscode_port,
                    git=args.git,
                    ssh=args.ssh,
                    docker=args.docker,
                    dangerously_skip_permissions=args.dangerously_skip_permissions,
                    continue_last=args.continue_last,
                    resume_id=args.resume_id,
                    model=args.model,
                    permission_mode=args.permission_mode,
                    print_prompt=args.print_prompt,
                    add_dirs=args.add_dirs,
                    ide=args.ide,
                )
                return manager.cmd_start(args.name, opts)
            case "stop":
                return manager.cmd_stop(args.name)
            case "restart":
                return manager.cmd_restart(args.name)
            case "remove":
                return manager.cmd_remove(args.name, args.force or args.yes)
            case "info":
                return manager.cmd_info()
            case "install":
                return manager.cmd_install(args.image)
            case "image":
                match args.image_action:
                    case "list":
                        return manager.cmd_image_list()
                    case "install":
                        return manager.cmd_image_install(args.image)
                    case "install-all":
                        return manager.cmd_image_install_all()
                    case "update":
                        return manager.cmd_image_update(args.image)
                    case "remove":
                        return manager.cmd_image_remove(args.image, args.force)
                    case "build":
                        return manager.cmd_image_build(args.path, args.name, args.tag)
            case "logs":
                return manager.cmd_logs(args.name)
            case "version":
                from claudock.console import console
                console.print(f"[brand]claudock[/] [version]v{__version__}[/]")
                return 0
            case "config":
                match args.config_action:
                    case "show":
                        return manager.cmd_config_show()
                    case "path":
                        return manager.cmd_config_path()
                    case "edit":
                        return manager.cmd_config_edit()
            case "profile":
                match args.profile_action:
                    case "list":
                        return manager.cmd_profile_list()
                    case "create":
                        return manager.cmd_profile_create(args.name)
                    case "remove":
                        return manager.cmd_profile_remove(args.name, args.force or args.yes)
                    case "show":
                        return manager.cmd_profile_show(args.name)
            case _:
                parser.print_help()
                return 2
    except KeyboardInterrupt:
        log.warn("Interrupted.")
        return 130
    except Exception as exc:
        show_exception(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
