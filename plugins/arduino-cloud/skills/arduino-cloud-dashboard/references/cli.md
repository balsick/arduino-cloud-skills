# arduino-cloud-cli for dashboards (v0.8.0)

Source: https://github.com/arduino/arduino-cloud-cli · Docs:
https://docs.arduino.cc/arduino-cloud/arduino-cloud-cli/getting-started/

Install, credentials, the full command list (devices, OTA, tags, templates) and general quirks
are in the general skill's reference: `../../arduino-cloud/references/cli.md`. This file covers
only what dashboard building needs.

## Commands used by this skill

Global flags: `--format text|json|jsonmini|yaml`, `-v` (logs). Success is quiet; errors go to stderr.

```bash
arduino-cloud-cli thing list [--show-variables] [--ids a,b] [--tags k=v] [--device-id D]
arduino-cloud-cli thing show -t <thingID>
arduino-cloud-cli thing extract --id <thingID> --format json           # thing template
arduino-cloud-cli thing create --template t.json [--name N]
arduino-cloud-cli thing clone --clone-id <thingID> --name N
arduino-cloud-cli thing create-tags --id <thingID> --tags k=v
arduino-cloud-cli thing publish -t <thingID> -p <variable> -s <value>  # write a value
arduino-cloud-cli thing delete --id <thingID>

arduino-cloud-cli dashboard list [--show-widgets]
arduino-cloud-cli dashboard show -d <dashboardID>
arduino-cloud-cli dashboard extract --id <dashboardID> --format json   # dashboard template
arduino-cloud-cli dashboard create --template t.json [--name N] --override ph1=<thingID>,ph2=<thingID>
arduino-cloud-cli dashboard delete --id <dashboardID>
```

There is no dashboard/thing **update** and no command to add variables to an existing Thing.

## Dashboard template format

```json
{
  "name": "My dashboard",
  "pages": [{"id": "p1", "name": "Main", "position": 0, "icon": "dashboard_filled"}],
  "widgets": [{
    "type": "Gauge", "name": "Temperature",
    "width": 6, "height": 6, "x": 0, "y": 0,
    "width_mobile": 4, "height_mobile": 4, "x_mobile": 0, "y_mobile": 0,
    "page_id": "p1",
    "variables": [{"thing_id": "greenhouse", "variable_id": "temperature"}],
    "options": {"min": 0, "max": 50}
  }]
}
```

How the CLI resolves it (`internal/template/load.go`):
- `variables[].thing_id` is a **placeholder**; every placeholder must be mapped with
  `--override placeholder=<real thing UUID>`. Putting the real UUID directly in the template fails
  ("no override provided"), because the override value must differ from the placeholder.
- `variables[].variable_id` is the **variable_name**, not an ID; the CLI looks it up on the Thing.
- Widget and page IDs are regenerated; `page_id` refers to a template page `id` (missing → page "0").
  A widget whose `page_id` is unknown is left unresolved and the whole create fails with 400.
- `Advanced Chart` options `aggregation`/`format`/`axes` and `Image Map`
  `markersSettings[].property` use `"placeholder:variable_name"` keys, rewritten to property IDs.
- `options` keys `created_by`, `thingId`, `properties` are removed; everything else is sent as is.
- Mobile fields are optional; without them the dashboard stores no mobile layout.
- Templates from `dashboard extract` use placeholders like `<thing-name-slug>-<last 5 of UUID>`
  and can be fed back to `dashboard create` with matching overrides — the quickest way to clone.

## Thing template format

```json
{
  "name": "Claude - Greenhouse",
  "timezone": "Europe/Rome",
  "tags": [{"created_by": "claude-dashboard-skill"}],
  "variables": [
    {"name": "temperature", "variable_name": "temperature", "type": "TEMPERATURE_C",
     "permission": "READ_ONLY", "update_strategy": "ON_CHANGE", "update_parameter": 0}
  ]
}
```

## Quirks

- API errors are printed as `400 Bad Request  (%!s(*string=0x…))` — the body is lost. Bisect the
  template (name, tags, one variable at a time). Known 400 causes: Thing name with characters other
  than letters/digits/space/`_.-`, or longer than 64 chars.
- Dashboard names accept emoji and unicode; Thing names do not.
- `thing publish` works only on READ_WRITE variables (READ_ONLY → `401 Unauthorized`). Handy to
  put sample values on a test Thing before checking a dashboard visually.
- The web app switches to the stored mobile layout on narrow windows (seen at 420px); without mobile fields there is none.
- `--override` is a `k=v,k=v` map: placeholder names must not contain `=` or `,`.
- In zsh, don't pass a multi-word command through an unquoted variable (no word splitting).
