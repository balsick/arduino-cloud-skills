# arduino-cloud-skills

Claude Code marketplace with skills for [Arduino Cloud](https://app.arduino.cc).

## Plugins

### `arduino-cloud`

- **arduino-cloud** — general Arduino Cloud work through
  [`arduino-cloud-cli`](https://github.com/arduino/arduino-cloud-cli): "how many devices are
  online?", which Things use a board, variable types/permissions, publishing a value, binding,
  tags, creating/deleting devices and Things, OTA updates, templates. Destructive or
  hardware-moving actions are confirmed first; Things/devices it creates are `Claude - …`, tagged
  `created_by=claude-arduino-cloud-skill`.
- **arduino-cloud-dashboard** — describe a dashboard in natural language ("temperature and humidity
  at the top, a history chart, pump controls on a second tab") and Claude builds it on Arduino
  Cloud with [`arduino-cloud-cli`](https://github.com/arduino/arduino-cloud-cli): picks widgets for
  your Things' variables, lays them out for desktop and mobile, creates the dashboard and links it.
  Everything it creates is recognizable (`🤖 Claude · …` dashboards, `Claude - …` Things tagged
  `created_by=claude-dashboard-skill`).

Requirements: `arduino-cloud-cli` on PATH, Python 3 (for the dashboard builder), an Arduino Cloud API key configured with
`arduino-cloud-cli credentials init`.

## Install

```
/plugin marketplace add <this repo>
/plugin install arduino-cloud@arduino-cloud-skills
```

For local development, symlink the skills instead:

```bash
for s in arduino-cloud arduino-cloud-dashboard; do
  ln -s "$PWD/plugins/arduino-cloud/skills/$s" ~/.claude/skills/$s
done
```
