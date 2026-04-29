# Project config: `.claudock.yml`

A `.claudock.yml` file at the root of your workdir lets you bake in defaults so you don't have to type the same `claudock start` flags every time.

## Resolution order

For a given `claudock start`, values are merged with this precedence (top wins):

1. CLI flags
2. `.claudock.yml` in the workdir (when `--cwd` or an explicit path is given)
3. Global `~/.claudock/config.yml`
4. Built-in defaults

## Example

```yaml
# ~/code/my-app/.claudock.yml

defaults:
  image: ghcr.io/helphyy/claudock-dev:latest
  profile: work
  network: bridge
  shell: zsh                # empty -> launches `claude` directly instead of a shell
  hostname: my-app
  log: false                # if true, --log is implied

docker:
  enable: false             # implies --docker (DANGER, see flags.md)
  socket: /var/run/docker.sock

vscode:
  enable: true              # implies --vscode
  port: 8080

git:
  url: git@github.com:you/my-app.git
  branch: main              # only used if /workspace is empty
  ssh: true                 # implies --ssh

ssh:
  enable: true              # forwards ~/.ssh
  dir: ~/.ssh               # custom path supported

env:
  STAGE: dev
  ANTHROPIC_LOG_LEVEL: warn

volumes:
  - ~/datasets:/workspace/datasets:ro

ports:
  - 8000:8000               # api
  - 5432:5432               # postgres for tests
```

## Use cases

- One project pinned to `claudock-data` for ML notebooks; another to `claudock-cloud` for IaC.
- Shared port mappings for the team's local stack.
- A specific branch checkout on first creation.
- Auto-enable `--vscode` for projects where you always want code-server.

## Editing

Just open `.claudock.yml` in the project root with any text editor. Claudock re-reads it on every `start`.

## Validation

`claudock config show` prints the **resolved** configuration, merging globals + project. Run it from inside the project to sanity-check what Claudock will actually do.
