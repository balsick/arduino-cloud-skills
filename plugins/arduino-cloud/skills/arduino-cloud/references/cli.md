# arduino-cloud-cli reference (v0.8.0)

Source: https://github.com/arduino/arduino-cloud-cli · Docs:
https://docs.arduino.cc/arduino-cloud/arduino-cloud-cli/getting-started/

## Install

No Homebrew formula. Download from the releases page, verify, put on PATH:

```bash
V=$(curl -s https://api.github.com/repos/arduino/arduino-cloud-cli/releases/latest | python3 -c 'import json,sys;print(json.load(sys.stdin)["tag_name"])')
A=macOS_ARM64   # or macOS_64bit, Linux_64bit, Linux_ARM64, Windows_64bit (.zip)
curl -sLO https://github.com/arduino/arduino-cloud-cli/releases/download/$V/arduino-cloud-cli_${V}_$A.tar.gz
curl -sLO https://github.com/arduino/arduino-cloud-cli/releases/download/$V/$V-checksums.txt
grep "_$A.tar.gz" $V-checksums.txt | shasum -a 256 -c -
tar xzf arduino-cloud-cli_${V}_$A.tar.gz arduino-cloud-cli && mv arduino-cloud-cli ~/.local/bin/
```

## Credentials

Lookup order: env vars `ARDUINO_CLOUD_CLIENT` + `ARDUINO_CLOUD_SECRET` (+ optional
`ARDUINO_CLOUD_ORGANIZATION`) → `arduino-cloud-credentials.{yaml,json}` in the current dir and its
parents → the Arduino data dir (`~/Library/Arduino15` on macOS, `~/.arduino15` on Linux).
`arduino-cloud-cli credentials find` says which one is used. Only the user runs `credentials init`.

## Commands

Global flags: `--format text|json|jsonmini|yaml`, `-v` (logs). Success is quiet; errors go to stderr.
Tags are always `--tags k=v,k2=v2`.

### Devices

```bash
arduino-cloud-cli device list [-d id1,id2] [-s ONLINE|OFFLINE|UNKNOWN] [--tags k=v]
arduino-cloud-cli device show -d <deviceID>
arduino-cloud-cli device list-fqbn                       # boards the Cloud supports
arduino-cloud-cli device create -n N -p <port> [-b <fqbn>] [-c <connection>] [-l true|false]
                                # provisions the secure element: board must be on the serial port
arduino-cloud-cli device create-generic -n N [-b <fqbn>] # password auth, no secure element (prints the secret key once)
arduino-cloud-cli device create-lora -n N -p <port> -b <fqbn> -f <frequencyPlanID>
arduino-cloud-cli device list-frequency-plans
arduino-cloud-cli device configure -p <port> -b <fqbn> -c <1 WiFi|2 Eth|3 NB-IoT|4 GSM|5 LoRaWan|6 CAT-M1|7 Cellular> [-f cfg]
arduino-cloud-cli device create-tags (-i <deviceID> | --ids a,b) --tags k=v
arduino-cloud-cli device delete-tags -i <deviceID> --keys k1,k2
arduino-cloud-cli device delete (-i <deviceID> | --tags k=v)       # --tags deletes ALL matches
```

`device list` fields: `name, id, board, fqbn, type, status, connection_type, serial_number,
thing_id` (absent when unbound), `unique_hardware_id`, `locked`. `type: "phone"` = the IoT Remote
app on a phone/tablet.

### Things

```bash
arduino-cloud-cli thing list [--show-variables] [-i a,b] [--tags k=v] [-d <deviceID>]
arduino-cloud-cli thing show -t <thingID>              # device, sketch_id, timezone, webhook
arduino-cloud-cli thing extract --id <thingID> --format json   # template: variables with type/permission
arduino-cloud-cli thing create --template t.json [--name N]
arduino-cloud-cli thing clone --clone-id <thingID> --name N
arduino-cloud-cli thing bind -i <thingID> -d <deviceID>
arduino-cloud-cli thing create-tags -i <thingID> --tags k=v
arduino-cloud-cli thing delete-tags -i <thingID> --keys k1,k2
arduino-cloud-cli thing publish -t <thingID> -p <variable> -s <value>
arduino-cloud-cli thing publish -t <thingID> -m 'light={"bri": 100.0, "hue": 203.0, "sat": 100.0, "swi": true},msg=hello'
arduino-cloud-cli thing delete (-i <thingID> | --tags k=v)         # --tags deletes ALL matches
```

`thing list --show-variables` returns only variable **names**; `thing extract` adds `type`,
`permission`, `update_strategy`. No command returns variable values.

### Dashboards

```bash
arduino-cloud-cli dashboard list [--show-widgets]
arduino-cloud-cli dashboard show -d <dashboardID>
arduino-cloud-cli dashboard extract --id <dashboardID> --format json
arduino-cloud-cli dashboard create --template t.json [--name N] --override ph=<thingID>
arduino-cloud-cli dashboard delete --id <dashboardID>
```

For creating dashboards and the dashboard template format, see the `arduino-cloud-dashboard` skill.

### OTA

```bash
arduino-cloud-cli ota upload -d <deviceID> --file sketch.bin [--deferred] [--no-header]
arduino-cloud-cli ota mass-upload -b <fqbn> (-d id1,id2 | --device-tags k=v) --file sketch.bin [--deferred]
arduino-cloud-cli ota status (-d <deviceID> | -o <otaID> | --ota-ids a,b) [-l 10] [-s desc]
arduino-cloud-cli ota cancel -o <otaID>
arduino-cloud-cli ota header-encode / header-decode     # inspect or prepare .ota headers
```

The `.bin` comes from compiling the sketch for the device FQBN (e.g.
`arduino-cli compile -b <fqbn> --output-dir out`). The CLI adds the OTA header and compression
unless `--no-header`. The device must be online, unless `--deferred` (it waits up to 1 week).

### Custom templates (Thing + dashboard + device bundles)

```bash
arduino-cloud-cli template list
arduino-cloud-cli template export -t <templateID> -d <outDir>
arduino-cloud-cli template import -f <file.tino>
arduino-cloud-cli template apply -t <templateID> -d <deviceID> -p <namePrefix> -n SECRET_SSID=..,SECRET_OPTIONAL_PASS=..
```

`-n` carries Wi-Fi credentials, so the user types that command.

## Thing template format

```json
{
  "name": "Claude - Greenhouse",
  "timezone": "Europe/Rome",
  "tags": [{"created_by": "claude-arduino-cloud-skill"}],
  "variables": [
    {"name": "temperature", "variable_name": "temperature", "type": "TEMPERATURE_C",
     "permission": "READ_ONLY", "update_strategy": "ON_CHANGE", "update_parameter": 0}
  ]
}
```

Common variable `type`s: `STATUS` (bool), `INT`, `FLOAT`, `CHARSTRING`, `LOCATION`, `COLOR_HSB`,
`HOME_COLORED_LIGHT`, `HOME_DIMMED_LIGHT`, `HOME_SWITCH`, `TIME`, `SCHEDULE`, and unit types such
as `TEMPERATURE_C`, `RELATIVE_HUMIDITY`, `PERCENTAGE`. To get a type spelled right, `thing extract`
an existing Thing that has one. `permission`: `READ_ONLY` | `READ_WRITE`. `update_strategy`:
`ON_CHANGE` (`update_parameter` = threshold) | `TIMED` (seconds).

## Quirks

- API errors are printed as `400 Bad Request  (%!s(*string=0x…))`: the body is lost. Bisect the
  input (name, tags, one variable at a time). Known 400 causes: Thing name with characters other
  than letters/digits/space/`_.-`, or longer than 64 chars.
- Dashboard names accept emoji and unicode; Thing names do not.
- `thing publish` works only on READ_WRITE variables (READ_ONLY → `401 Unauthorized`).
- Map flags (`--tags`, `--override`, `-m`) are `k=v,k=v`: keys and values must not contain `=`
  or `,` (except inside the JSON of `-m`).
- In zsh, a multi-word command in an unquoted variable is not split: use `${=var}` or an array.

## REST API (values, history, connection events)

The CLI can't read values or history. `scripts/cloud_api.py` (in the skill dir) calls
`https://api2.arduino.cc` using the **same credentials as the CLI** (env vars or
`arduino-cloud-credentials.yaml|json`). It gets an OAuth token (client_credentials,
audience `https://api2.arduino.cc/iot`), sends `X-Organization` when `organization` is set, and
prints the JSON response. It never prints the secret or the token. Stdlib only, no pip install.

```bash
API=~/.claude/skills/arduino-cloud/scripts/cloud_api.py
python3 $API GET  <path>              # GET
python3 $API POST <path> '<json body>'  # POST/PUT/DELETE likewise
```

Verified endpoints (read-only):

| what | call |
|---|---|
| Things with variables, `last_value`, `value_updated_at`, property `id` | `GET /iot/v2/things?show_properties=true` |
| one Thing's variables | `GET /iot/v2/things/{thingID}/properties` |
| devices with `last_activity_at`, `device_status`, `wifi_fw_version`, `ota_available`, `events` | `GET /iot/v2/devices` |
| device connection history (`r_status` CONNECTED/DISCONNECTED, newest first) | `GET /iot/v2/devices/{deviceID}/events?limit=500&start=<ISO8601>` |
| aggregated history of one variable | `GET /iot/v2/things/{thingID}/properties/{propertyID}/timeseries?from=<ISO>&to=<ISO>&interval=<seconds>` → `{"data":[{"time","value"}]}` |
| raw history, many variables in one call | `POST /iot/v2/series/batch_query_raw` `{"requests":[{"q":"property.<propertyID>","from":"<ISO>","to":"<ISO>","sort":"ASC","series_limit":1000}],"resp_version":1}` → `responses[].times/values` |

Notes:
- `series/batch_query_raw` and `timeseries` need the property **id** (UUID), not the variable
  name. Get it from `things?show_properties=true`.
- `last_value` is `"N/A"` for variables that were never set.
- Things with no variables (`properties: []`) have no value history. Only device events exist for them.
- Writes (not tested by this skill): `PUT /iot/v2/things/{id}/properties/{pid}/publish` `{"value":...}`.
  Prefer `thing publish`. The same confirmation rules apply.

### Recipe: "anything strange in the last N hours?"

1. `GET /iot/v2/devices`: who is online, who has `last_activity_at` inside the window.
2. For each device active in the window: `devices/{id}/events?start=<now-N h>`. Count
   DISCONNECTED→CONNECTED cycles, then compare with a longer baseline (e.g. 14 days) to see
   whether it's unusual.
3. `things?show_properties=true`: variables with `value_updated_at` inside the window. For
   those, `batch_query_raw` over the window and look for spikes, flat lines, gaps, out-of-range values.
4. Also flag devices that went quiet (last activity just before the window) and
   `ota status` jobs inside the window.
