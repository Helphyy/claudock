# Images: the seven official variants

All images live on `ghcr.io/helphyy/`. Pull one, or use the `claudock image` subcommand which understands variant shorthands (`dev`, `cloud`, ...).

## Variants

| Variant | Size | Purpose |
|---------|------|---------|
| `claudock-minimal:latest`  | 2.3 GB  | Base: Claude Code + zsh + code-server + Firefox + Chromium + minimal Unix tools. |
| `claudock-dev:latest`      | 6.1 GB  | + Python/Node/Go/Rust/Java/Ruby/Crystal/Zig/Lua, Docker CLI, gh/glab, lazygit, mise, DB clients. |
| `claudock-cloud:latest`    | 7.3 GB  | + AWS/GCP/Azure CLIs, Terraform, Vault, Consul, Nomad, Packer, kubectl, Helm, k9s, Trivy, Ansible. |
| `claudock-security:latest` | 6.5 GB  | + nmap suite, ProjectDiscovery (nuclei/subfinder/httpx/katana), feroxbuster, code-audit (gitleaks/trufflehog/syft/grype/semgrep/bandit/bearer/gosec), volatility3, bbot, tshark. |
| `claudock-data:latest`     | 7.0 GB  | + JupyterLab, pandas/polars/duckdb, scikit-learn/xgboost/lightgbm/statsmodels, Quarto, geopandas, spaCy, ibis, great-expectations, dbt-duckdb/postgres. |
| `claudock-doc:latest`      | 7.9 GB  | + LaTeX (medium + bibtex/science/publishers), pandoc + pandoc-crossref, Hugo, mdBook, Quarto, marp, d2, plantuml, mkdocs, sphinx, vale, LanguageTool, LibreOffice. |
| `claudock-full:latest`     | 10.9 GB | dev + cloud + security combined. |

All variants ship Claude Code (native binary), code-server with the official `Anthropic.claude-code` extension, oh-my-zsh + plugins, asciinema for session recording, and Firefox + Chromium for headed browsing via X11 forwarding.

## Picking a variant

- Writing code, no infra/security: `dev`.
- DevOps, k8s, IaC: `cloud`.
- Pentest, audit, forensics: `security`.
- Notebooks, ML, analytics: `data`.
- Papers, docs, slides: `doc`.
- All of the above on one disk: `full`.
- Just want the smallest thing that runs Claude: `minimal`.

## Default image

Set in `~/.claudock/config.yml`:

```yaml
default_image: dev          # or full, or any of the seven, or a full image ref
images:
  registry: ghcr.io/helphyy
  tag: latest
```

A bare variant name is expanded to `<registry>/claudock-<variant>:<tag>`.

## `claudock image` subcommand

```bash
claudock image list                  # pretty table of all variants + local presence
claudock image install dev           # pull one
claudock image install-all           # pull all seven
claudock image update full           # re-pull a tag (latest moves)
claudock image remove dev            # docker rmi
claudock image build ./my-image     # build a custom Dockerfile + register it locally
```

The `install`/`update`/`remove`/`build` verbs accept either a variant shorthand or a full image ref.

## Custom images

Drop your own Dockerfile in a folder and:

```bash
claudock image build ./my-image --name claudock-myteam --tag v1
claudock start mysession --image claudock-myteam:v1
```

Then in `config.yml`:

```yaml
default_image: claudock-myteam:v1
```
