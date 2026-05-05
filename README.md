# copilot-setup

A Textual TUI dashboard for viewing and managing your GitHub Copilot CLI configuration.
Browse MCP servers, plugins, skills, agents, settings, and more — toggle, upgrade,
and remove plugins or MCP servers without leaving the terminal.

![copilot-setup dashboard](https://raw.githubusercontent.com/ericchansen/copilot-setup/main/docs/screenshot.png)

## Installation

Install as an isolated CLI tool with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install copilot-setup
```

Or run directly without installing:

```bash
uvx copilot-setup
```

For **development** from a local clone:

```bash
git clone https://github.com/ericchansen/copilot-setup.git
cd copilot-setup
uv tool install -e .           # editable install
uv tool install ruff pytest    # dev tools
```

The `-e` flag enables editable mode — code changes are reflected immediately without reinstalling.

Requires Python ≥ 3.10.

> **Why `uv tool install` over `pip install`?** Global pip pollutes your system Python
> and causes version conflicts. `uv tool install` gives each tool its own isolated venv
> (like `pipx`, but faster). If you previously installed with `pip install copilot-setup`,
> clean it up with `pip uninstall copilot-setup` then reinstall via uv.

## Usage

```bash
copilot-setup           # Launch the TUI dashboard
copilot-setup doctor    # Probe MCP server health
```

**11 tabs** · **Instant filter** (`/`) · **Detail pane** · **Plugin management** · **Doctor health probes**

📖 **[Full documentation →](https://ericchansen.github.io/copilot-setup/)**

## Releasing

Releases are published to [PyPI](https://pypi.org/project/copilot-setup/) automatically via GitHub Actions when a version tag is pushed.

```bash
# 1. Update version in pyproject.toml
# 2. Commit and push
git commit -am "chore: bump version to X.Y.Z"
git push

# 3. Tag and push
git tag vX.Y.Z
git push origin vX.Y.Z
```

The workflow validates the tag matches `pyproject.toml`, runs lint + tests, builds the wheel, then publishes to TestPyPI and PyPI using [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) (OIDC).
