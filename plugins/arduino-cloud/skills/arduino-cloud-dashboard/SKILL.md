---
name: arduino-cloud-dashboard
description: Create Arduino Cloud (IoT Cloud) dashboards from a natural-language description using arduino-cloud-cli — picks widgets for the user's Thing variables, lays them out for desktop and mobile, and creates the dashboard. Use when the user asks to create, design, generate, clone or rework an Arduino Cloud dashboard, or to add widgets/charts/controls for their Arduino Things ("fammi una dashboard per la serra", "dashboard with a gauge for temperature and a switch for the pump").
---

# Arduino Cloud dashboards from natural language

You turn a description like *"a dashboard for the greenhouse: temperature and humidity at the top,
a history chart, and controls for the pump on a separate tab"* into a real dashboard on Arduino
Cloud, using `arduino-cloud-cli` and the bundled builder script.

Files in this skill:
- `scripts/build_dashboard.py` — compact spec → full template (defaults, validation, desktop +
  mobile layout, naming) and optional creation. Standard-library Python only.
- `references/widgets.md` — catalog of widget `type` strings, compatible variable types, sizes and
  `options`. **Read it before writing a spec** that uses options beyond the obvious.
- `references/cli.md` — dashboard commands, template format and dashboard quirks.

For anything else on Arduino Cloud (device status, publishing values, OTA, tags…) use the
`arduino-cloud` skill in this plugin; its `references/cli.md` has the full CLI reference.

## 0. Preflight

```bash
command -v arduino-cloud-cli && arduino-cloud-cli credentials find
```

- CLI missing → install it following `../arduino-cloud/references/cli.md` (download the GitHub
  release for the platform, verify the checksum, put the binary on PATH). Ask before installing.
- No credentials → **never ask for, type or store the client secret yourself.** Tell the user to
  create an API key at https://app.arduino.cc/api-keys and run `arduino-cloud-cli credentials init`
  themselves (or export `ARDUINO_CLOUD_CLIENT` / `ARDUINO_CLOUD_SECRET`). An empty `organization`
  means the personal space; an organization ID targets a shared/team space — confirm which one the
  user wants before creating anything in an organization.

## 1. Discover Things and variables

```bash
arduino-cloud-cli thing list --show-variables --format json      # names, ids, variable names
arduino-cloud-cli thing extract --id <thingID> --format json     # variable types + permissions
```

Map what the user said to concrete Things and variables. If a name is ambiguous or a variable the
user wants does not exist, ask — do not guess silently. The CLI **cannot add variables to an
existing Thing**; if variables are missing, either the user adds them in the web UI, or (only if
asked) you create a new Thing with `thing create` (see `references/cli.md`).

## 2. Design the dashboard

Pick widgets from the variable type and the user's intent (full list in `references/widgets.md`):

| variable | to monitor | to control (needs READ_WRITE) |
|---|---|---|
| numeric (INT, FLOAT, units) | `Value`, `Gauge` (bounded), `Percentage` (0–100 / battery / level), `Chart` (history), `Advanced Chart` (2–5 series together) | `Slider` (range), `Stepper` (fine steps) |
| INT/String enum | `Value` | `Value Selector` (≤4 choices), `Value Dropdown` (more) |
| STATUS (bool) | `Status` (state/alarm, green/red or icons), `LED` (simple indicator light) | `Switch` (toggle), `Push Button` (momentary) |
| CHARSTRING | `Value` | `Messenger` |
| LOCATION | `Map`, `Advanced Map` (track history) | – |
| COLOR_HSB (what users call "RGB"/"colore") | – | `Color` |
| HOME_COLORED_LIGHT / HOME_DIMMED_LIGHT | – | `Colored light` / `Dimmed light` (switch + brightness [+ color]) |
| TIME / SCHEDULE | – | `Time Picker`, `Scheduler` |
| none | `Sticky Note` (titles, instructions, markdown), `Link`, `Image` (https URL) | |

Layout guidelines (unless the user says otherwise):
- Reading order is spec order; the builder places each widget at the highest free spot.
  Typical order: KPIs (`Value`/`Gauge`/`Percentage`/`Status`) in a row, then charts, then controls.
  What the user says must be "at the top" goes first; an explanatory `Sticky Note` then goes at the
  end of the KPI row or below the charts, otherwise it can open the dashboard as a title/intro.
  A Sticky Note displays `options.title` and `options.content` (the widget `name` is not shown).
- Build **rows**: widgets side by side should share the same height and their widths should add up
  to 24 (e.g. 4 KPIs × `[6, 5]`, 3 × `[8, 5]`, 2 × `[12, 6]`). Set `size` explicitly for rows
  rather than mixing default sizes, which leaves ragged holes.
- Group widgets of the same room/device/topic together; give widgets human names in the user's
  language (e.g. "Temperatura serra", not `temp_1`), with units where useful.
- Set meaningful `min`/`max` for Gauge/Slider/Percentage from context (°C → e.g. -10..45).
- Many widgets (>~16) or mixed monitoring/control → use `pages` (tabs).
- Charts read best wide: `[24, 8]` alone or `[12, 8]` in pairs. Mobile (8 columns) is laid out
  automatically (spec order, gaps filled); set `size_mobile` only for special cases.

## 3. Write the spec and build

Write the spec to a working file (scratchpad), e.g. `greenhouse.dashboard.json`:

```json
{
  "name": "Serra",
  "things": {"serra": "Greenhouse"},
  "pages": [{"id": "monitor", "name": "Monitor", "icon": "dashboard_filled"},
            {"id": "control", "name": "Controlli", "icon": "shutter"}],
  "widgets": [
    {"type": "Gauge", "var": "serra:temperature", "name": "Temperatura (°C)", "page": "monitor",
     "options": {"min": -10, "max": 45}},
    {"type": "Percentage", "var": "serra:humidity", "name": "Umidità", "page": "monitor",
     "options": {"custom_icon": "water_drop", "showIcon": true}},
    {"type": "Advanced Chart", "vars": ["serra:temperature", "serra:humidity"],
     "name": "Andamento clima", "page": "monitor", "size": [24, 9],
     "options": {"multipleAxes": true}},
    {"type": "Switch", "var": "serra:pump", "name": "Pompa", "page": "control"}
  ]
}
```

- `things`: alias → Thing UUID **or exact Thing name**. Aliases are placeholders (`[A-Za-z0-9_-]`).
- `var` / `vars`: `"alias:variable_name"` (alias may be omitted when there is a single Thing).
- Optional per widget: `name`, `options`, `size`, `pos` ([x, y] desktop), `size_mobile`,
  `pos_mobile`, `page`.

```bash
python3 <skill-dir>/scripts/build_dashboard.py spec.json            # dry run: validate + template
python3 <skill-dir>/scripts/build_dashboard.py spec.json --create   # create on Arduino Cloud
```

The script resolves Things, checks every variable exists, warns on type mismatches, refuses control widgets on READ_ONLY variables,
fills Advanced Chart per-series options, lays out desktop and mobile, prefixes the name and prints
the dashboard URL. Fix every `error:`; treat `warning:` lines seriously (usually a wrong widget).

The dry run prints, per page, one line per widget and an ASCII map of the desktop grid (one letter
per widget, `.` empty, `#` overlap); add `--mobile-preview` for the phone layout. **Look at the map
before creating**: if rows are ragged or there are large empty areas, adjust `size`s and rerun.

For a simple, unambiguous request create directly. When you had to make significant guesses
(which Thing, which variables, what to control), show the planned widget list first and ask.

## 4. Verify and report

`--create` prints `{"id", "name", "url"}` — that means the API accepted it with all variables
resolved. `arduino-cloud-cli dashboard extract --id <id> --format json` is only needed to inspect
what was stored. Report the URL
`https://app.arduino.cc/dashboards/<id>` and a one-line summary of what is on it. If a browser is
available and the user is logged in, look at it on desktop and mobile width.

## Recognizable resources — always

- Every dashboard you create is named `🤖 Claude · <name>` (the script adds the prefix).
- Every Thing you create is named `Claude - <name>` (Thing names allow only letters, digits,
  space, `_ . -`, max 64 chars) and tagged `created_by=claude-dashboard-skill`.
- Find them later: `arduino-cloud-cli dashboard list | grep '🤖 Claude'`,
  `arduino-cloud-cli thing list --tags created_by=claude-dashboard-skill`.

## Changing an existing dashboard

The CLI has **no update command**. To change a dashboard: `dashboard extract` it, edit (or rebuild
the spec), create the new one, then **ask** before deleting the old one with
`dashboard delete --id`. Never delete or modify dashboards/Things you did not create unless the
user explicitly asks for that specific one. When extracting a dashboard to clone it, strip the UI
bookkeeping keys listed in `references/widgets.md` (they live inside `options`).
