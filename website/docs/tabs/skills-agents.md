---
sidebar_position: 3
title: Skills & Agents
---

# Skills & Agents Tabs

The **Skills** and **Agents** tabs share the same structure. Both display YAML-defined extensions that add specialized capabilities to Copilot CLI — skills provide domain-specific workflows, while agents define autonomous task runners.

## Sources

| Type | User directory | Plugin-bundled directory |
|------|---------------|------------------------|
| **Skills** | `~/.copilot/skills/` | `~/.copilot/installed-plugins/<plugin>/skills/` |
| **Agents** | `~/.copilot/agents/` | `~/.copilot/installed-plugins/<plugin>/agents/` |

## Columns

| Column | Description |
|--------|-------------|
| **Name** | Skill or agent name (from YAML filename or `name` field) |
| **Source** | `user` for files in the user directory, or the plugin name for bundled items |
| **Description** | Short description from the YAML `description` field |

## Detail Pane

Selecting a skill or agent displays its full YAML content:

- **Name** and **description**
- **Triggers** — keywords or phrases that activate the skill/agent
- **Allowed tools** — which tools the skill/agent is permitted to use
- **Location** — `user` or the parent plugin name
- Any additional YAML fields defined in the file

## Plugin-Bundled Discovery

copilot-setup scans each installed plugin's directory for bundled skills and agents. During data loading, the app walks:

```
~/.copilot/installed-plugins/
  └── <plugin-name>/
      ├── skills/
      │   ├── my-skill.md
      │   └── another-skill.md
      └── agents/
          └── my-agent.md
```

Each discovered file is attributed to its parent plugin in the **Source** column. This lets you see at a glance which skills and agents come from which plugin versus your own user-defined files.

## Read-Only

Both tabs are read-only — they display the YAML files as they exist on disk. To add, edit, or remove skills and agents, modify the YAML files directly in the appropriate directory.
