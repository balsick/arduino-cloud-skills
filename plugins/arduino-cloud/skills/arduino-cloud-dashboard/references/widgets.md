# Arduino Cloud widget catalog

Derived from ~650 real widgets extracted with `arduino-cloud-cli dashboard extract` (Sept 2026)
plus create/extract round-trips. The CLI does **not** validate `type` or `options`; the API accepts
unknown keys silently, so a typo means a widget that silently falls back to defaults.

`type` strings are **case-sensitive** and must match exactly (note `Colored light`, `Dimmed light`).

Grid: desktop is **24 columns**, mobile is **8 columns**. Units are grid cells; `y` grows downward.

## Keys to never write

The UI stores bookkeeping keys **inside `options`**; they are harmless but useless in templates. Do not copy
them from extracted dashboards: `id`, `icon`, `section`, `premium`, `lock`, `readOnly`, `linked`,
`value`, `name`, `size`, `kind`, `layout`, `description`, `tags`, `supportedPermissions`,
`supportedVariableTypes`, `allowSpecializedType`, `selectedTab`, `lastUpdate`.
`created_by`, `thingId`, `properties` are stripped by the CLI anyway.

Common optional keys valid on most linked widgets: `frameless` (bool, hide card frame),
`showThing` (bool, show the Thing name under the title).

## Monitoring (read)

| type | variables | default size d / m | options |
|---|---|---|---|
| `Value` | 1, any numeric / `CHARSTRING` / bool | 4×3 / 4×3 | `decimals` (int), `round` (`"round"`\|`"truncate"`), `showIcon` (bool), `custom_icon` (icon name, e.g. `"temperature"`), `icon_color` (hex) |
| `Gauge` | 1 numeric | 6×6 / 4×4 | `min`, `max` |
| `Percentage` | 1 numeric | 5×5 / 4×5 (at 4×4 mobile only the icon shows) | `min`, `max`, `showIcon`, `custom_icon` (`battery_0`, `water_drop`, `light_luminosity`, `cloud-filled`, `wind`…), `isThresholdActive` (bool), `thresholdType` (`"below"`\|`"above"`), `thresholdValue`, `thresholdColor` (hex) |
| `LED` | 1 bool (`STATUS`) | 2×2 / 4×2 | `mode`: `"Color 1"` \| `"Color 2"` \| `"Both Colors"` |
| `Status` | 1 bool | 2×2 / 4×2 | `mode`: `"On / Off"` \| `"Icons"` (docs also mention `"True / False"`, not seen in real data); with `"Icons"`: `enableCustom` (bool), `trueIcon`, `falseIcon` (e.g. `"power"`) |
| `Chart` | 1 numeric | 9×6 / 8×6 | `interpolation`: `"spline"` \| `"line"` |
| `Advanced Chart` | 1–5 numeric | 10×9 / 8×9 | see below |
| `Map` | 1 `LOCATION` | 8×8 / 8×8 | – |
| `Advanced Map` | 1 `LOCATION` | 10×9 / 8×9 | `markerType`: `"CONNECTED_DOTS"` \| `"SIMPLE_LINE"`, `markersColor` (hex), `showIcon`, `pinIcon` (e.g. `"train"`) |
| `Image Map` | 0–N numeric/string/bool | 12×10 / 8×9 | see below |

## Control (write — variable must be READ_WRITE; on READ_ONLY the widget renders as an error ⚠️)

| type | variables | default size d / m | options |
|---|---|---|---|
| `Switch` | 1 bool | 3×3 / 4×4 | `showLabels` (bool, ON/OFF text) |
| `Push Button` | 1 bool | 4×4 / 4×4 | – |
| `Slider` | 1 numeric | 6×4 / 8×4 | `min`, `max`, `vertical` (bool) |
| `Stepper` | 1 numeric (also `TIME`) | 4×3 / 4×3 | `min`, `max`, `step` (can be fractional, e.g. 0.5) |
| `Value Selector` | 1 `INT` or `CHARSTRING` | 6×3 / 8×3 | `values`: `[{"label": "OFF", "value": "0"}, …]` (**required**, values are strings, must be unique), `showIcons`, `customizeColors` |
| `Value Dropdown` | 1 `INT` or `CHARSTRING` | 5×3 / 8×3 | `values` as above (**required**) |
| `Messenger` | 1 `CHARSTRING` | 8×12 / 8×10 | – |
| `Color` | 1 `COLOR_HSB` | 6×7 / 8×7 | – |
| `Colored light` | 1 `HOME_COLORED_LIGHT` | 7×8 / 8×7 | – (min 4×5, max 12×12) |
| `Dimmed light` | 1 `HOME_DIMMED_LIGHT` | 7×8 / 8×7 | – |
| `Time Picker` | 1 `TIME` | 7×5 / 8×5 | `display`: `"Date and Time"` \| `"Date"` \| `"Time"`; `dateFormat`: `"dd / MM / yyyy"` \| `"yyyy / MM / dd"`; `timeFormat`: `"HH : mm : ss"` \| `"HH : mm"` |
| `Scheduler` | 1 `SCHEDULE` | 10×7 / 8×7 | `display`: `"Date and Time"` \| `"Time only"`; `dateFormat`, `timeFormat` as Time Picker |

## Static (no variables)

| type | default size d / m | options |
|---|---|---|
| `Sticky Note` | 6×4 / 8×auto (height from text; builder warns on overflow) | `title`, `content` (markdown), `color` (`#FFEAA1` yellow, `#B4FFD6` green, `#FFBEDD` pink, `#A0EEFF` blue, `#FFFFFF`), `visibility`: `"Title + Paragraph"` \| `"Title Only"` \| `"Paragraph Only"` |
| `Link` | 7×4 / 8×4 | `url` (**https://** required), `label`, `color` (hex), `custom_icon`, `showFullUrl` (bool) |
| `Image` | 6×6 / 8×6 | `image`: `{"source": "url", "url": "https://…", "autoRefresh": 30}` (seconds, optional), `fitting`: `"fit"` \| `"fill"`, `background` (bool, grey backdrop) |

Uploaded images (`"source": "upload"`) point to Arduino media storage and cannot be created from the
CLI; use `source: url` with an HTTPS URL.

## Advanced Chart

Per-variable options are keyed by `"<thing placeholder>:<variable_name>"` — the same placeholder
used in `variables[].thing_id`. The CLI rewrites these keys to property UUIDs.

```json
"options": {
  "aggregation": {"lab:temperature": {"value": "AVG"}, "lab:humidity": {"value": "AVG"}},
  "format": {
    "lab:temperature": {"color": {"color": "#0CA1A6"}, "type": {"label": "Line", "value": "line"}},
    "lab:humidity":    {"color": {"color": "#622998"}, "type": {"label": "Line", "value": "line"}}
  },
  "axes": {"lab:temperature": {"label": "°C"}, "lab:humidity": {"label": "%"}},
  "multipleAxes": true,  "showLegend": true,  "showYAxes": true
}
```

Aggregations seen: `AVG`, `MIN`, `MAX` (UI also shows labels "Average", …; `label` is optional).
Palette used by the UI: `#0CA1A6 #622998 #2D65F4 #EC4635 #FE9B4F`. `build_dashboard.py` fills all
three maps automatically; set `options.aggregation_all` to change the aggregation for every series.

## Image Map

Needs a background image and markers. Markers of kind `property` reference a variable with the
same `"placeholder:variable_name"` string; kind `static` markers are plain labels.

```json
"options": {
  "image": {"source": "url", "url": "https://example.com/floorplan.png"},
  "markersSettings": [
    {"id": "<uuid4>", "kind": "static", "label": "Room A", "position": {"x": 10, "y": 42}, "size": "s"},
    {"id": "<uuid4>", "kind": "property", "property": "lab:temperature",
     "position": {"x": 60, "y": 50}, "size": "s",
     "customColor": true, "colorThresholds": {"lower": {"value": 18, "color": "#2D65F4"},
                                              "greater": {"value": 26, "color": "#EC4635"}}},
    {"id": "<uuid4>", "kind": "property", "property": "lab:alarm", "position": {"x": 80, "y": 20},
     "size": "s", "style": "symbols", "enableCustom": true,
     "trueIcon": "close", "trueColor": "#EC4635", "falseIcon": "checkmark_outline", "falseColor": "#32a852"}
  ]
}
```

`position` is a percentage of the image (0–100). Also list every referenced variable in the widget
`variables` array.

## Pages

A dashboard can have tabs (`pages`). Page icons seen: `dashboard_filled`, `shutter`, `small`.
Widgets reference a page by the template page `id`; without pages everything sits on page `"0"`.

## Variable types (for `thing create`)

`INT`, `FLOAT`, `CHARSTRING`, `STATUS` (bool), `LOCATION`, `COLOR_HSB`, `TIME`, `SCHEDULE`,
`HOME_COLORED_LIGHT`, `HOME_DIMMED_LIGHT`, `HOME_SWITCH`, `HOME_SMART_PLUG`, plus many unit types
that behave as numbers: `TEMPERATURE_C`, `PERCENTAGE_RELATIVE_HUMIDITY`, `PERCENTAGE_BATTERY_LEVEL`,
`ILLUMINANCE`, `VOLT`, `AMPERE`, `WATT`, `PASCAL`, `METER`, … (full enum in the IoT API OpenAPI spec,
schema `property.type`). Permissions: `READ_ONLY`, `READ_WRITE`. Update strategy: `ON_CHANGE`
(with `update_parameter` = min delta) or `TIMED` (`update_parameter` = seconds).
