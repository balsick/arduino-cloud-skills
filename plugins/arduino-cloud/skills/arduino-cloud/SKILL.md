---
name: arduino-cloud
description: Work with Arduino Cloud (IoT Cloud) through arduino-cloud-cli — list devices and their online/offline status, inspect Things and their variables, publish values to variables, bind Things to devices, manage tags, create/delete devices and Things, run OTA firmware updates and apply templates. Use for any Arduino Cloud question or action that is not about designing a dashboard ("quanti device ho online?", "which Things use the GIGA?", "turn on the led on Cloud Blink", "OTA this .bin to all my Optas"). For creating or reworking dashboards use arduino-cloud-dashboard.
---

# Arduino Cloud with arduino-cloud-cli

You answer questions about the user's Arduino Cloud account and act on it with
[`arduino-cloud-cli`](https://github.com/arduino/arduino-cloud-cli). The full command reference
(install, credentials, every command and flag, Thing template format, quirks) is in
`references/cli.md`. **Read it** before anything beyond a list/show.

Dashboards → use the `arduino-cloud-dashboard` skill (same plugin), which has its own builder.

## 0. Preflight

```bash
command -v arduino-cloud-cli && arduino-cloud-cli credentials find
```

- CLI missing → install it following `references/cli.md`. Ask before installing.
- No credentials → **never ask for, type, print or store the client secret yourself.** Tell the
  user to create an API key at https://app.arduino.cc/api-keys and run
  `arduino-cloud-cli credentials init` themselves (or export `ARDUINO_CLOUD_CLIENT` /
  `ARDUINO_CLOUD_SECRET`). An empty `organization` means the personal space; an organization ID
  targets a shared/team space. Confirm which space before changing anything in an organization.

## 1. Reading: answer from JSON

Always use `--format json` and compute the answer with a short `python3 -c` (or `jq` if present)
rather than eyeballing long output. For example:

```bash
# how many devices are online, and which ones
arduino-cloud-cli device list --format json | python3 -c '
import json,sys,collections; d=json.load(sys.stdin)
print(len(d), dict(collections.Counter(x["status"] for x in d)))
print([x["name"] for x in d if x["status"]=="ONLINE"])'
```

| question | command |
|---|---|
| devices, status, board, Thing bound | `device list [-s ONLINE\|OFFLINE\|UNKNOWN] [--tags k=v]` |
| one device | `device show -d <deviceID>` |
| Things, their device and variable names | `thing list --show-variables [--device-id D] [--tags k=v]` |
| variable types and permissions | `thing extract --id <thingID>` |
| Thing details (device, sketch, timezone) | `thing show -t <thingID>` |
| dashboards | `dashboard list [--show-widgets]` |
| OTA history of a device | `ota status -d <deviceID>` |
| supported boards | `device list-fqbn` |

Joining data: `device list` gives `thing_id`; `thing list` gives `device_id`. Match on those IDs,
not on names, since names are not unique. Phones/tablets appear as devices with `type: "phone"`;
mention them separately when counting "boards".

The CLI **cannot read variables' current or historical values**, connection history or last
activity. For those, use the REST API through `scripts/cloud_api.py` (same credentials as the
CLI, read-only calls need no confirmation, never prints the secret or token):

```bash
python3 ~/.claude/skills/arduino-cloud/scripts/cloud_api.py GET '/iot/v2/things?show_properties=true'
```

| question | REST call |
|---|---|
| current values, when each was last updated | `GET /iot/v2/things?show_properties=true` |
| last activity of every device | `GET /iot/v2/devices` |
| connects/disconnects of a device | `GET /iot/v2/devices/{id}/events?start=<ISO>` |
| a variable's history | `POST /iot/v2/series/batch_query_raw` or `GET .../properties/{pid}/timeseries` |

Endpoints, body shapes and an "anything strange in the last N hours?" recipe are under
**REST API** in `references/cli.md`.

## 2. Acting: confirm first

Read-only commands need no confirmation. For anything that changes the account:

- **Publishing a value** (`thing publish`) can move real hardware (relays, motors, locks). State
  what will be set where and confirm, unless the user gave the exact Thing, variable and value.
  It works only on READ_WRITE variables.
- **Create / bind / tag**: OK to do when asked. Follow the naming rules below.
- **Delete** (`device delete`, `thing delete`, `dashboard delete`), **OTA** (`ota upload`,
  `ota mass-upload`), **tag-based bulk operations** (`--tags` on delete, `--device-tags` on OTA):
  list exactly which resources match first, show that list, and get an explicit yes. Never touch
  resources you did not create unless the user named them.
- **OTA**: check the `.bin` was built for the device's FQBN (`device show`); for `mass-upload`
  pass `--fqbn` and verify every target has it. Then follow progress with `ota status`.
- `device create` / `device configure` need the board on a local serial port (`--port`), and
  `device configure` needs a sketch with the Network Configurator. Ask the user to plug it in.
- `template apply --network-credentials` takes Wi-Fi passwords/device keys: let the user type
  that command, as with the API secret.

There is **no update command** for Things or dashboards, and no command to add variables to an
existing Thing. To change one: `extract` → edit → `create` the new one → ask before deleting
the old one. Otherwise the user does it in the web UI.

## Recognizable resources: always

- Things you create: `Claude - <name>` (letters, digits, space, `_ . -`, max 64 chars),
  tagged `created_by=claude-arduino-cloud-skill`.
- Devices you create: `Claude - <name>`, tagged the same way (`device create-tags`).
- Dashboards are created by `arduino-cloud-dashboard` (`🤖 Claude · <name>`, Things tagged
  `created_by=claude-dashboard-skill`).
- Find them later:
  `thing list --tags created_by=claude-arduino-cloud-skill`,
  `device list --tags created_by=claude-arduino-cloud-skill`.

## Reporting

Answer the question first (the number, the name, the state), then the details that support it.
Link resources: `https://app.arduino.cc/things/<id>`, `https://app.arduino.cc/devices/<id>`,
`https://app.arduino.cc/dashboards/<id>`. If a command fails, show its error. API errors often
lose their body (see Quirks in `references/cli.md`), so say what you tried next.
