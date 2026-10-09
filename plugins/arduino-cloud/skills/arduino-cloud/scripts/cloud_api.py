#!/usr/bin/env python3
"""Minimal Arduino Cloud REST API client that reuses arduino-cloud-cli credentials.

Usage:
  cloud_api.py GET  /iot/v2/things?show_properties=true
  cloud_api.py POST /iot/v2/series/batch_query_raw '{"requests":[...]}'

Prints the JSON response on stdout. Never prints the client secret or the token.
Credentials: ARDUINO_CLOUD_CLIENT / ARDUINO_CLOUD_SECRET / ARDUINO_CLOUD_ORGANIZATION env vars,
else arduino-cloud-credentials.yaml|json in cwd and its parents, else the Arduino data dir.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api2.arduino.cc"


def _parse_flat_yaml(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_credentials():
    if os.environ.get("ARDUINO_CLOUD_CLIENT") and os.environ.get("ARDUINO_CLOUD_SECRET"):
        return (os.environ["ARDUINO_CLOUD_CLIENT"], os.environ["ARDUINO_CLOUD_SECRET"],
                os.environ.get("ARDUINO_CLOUD_ORGANIZATION", ""))
    dirs = [Path.cwd(), *Path.cwd().parents,
            Path.home() / "Library/Arduino15", Path.home() / ".arduino15"]
    for d in dirs:
        for ext in ("yaml", "json"):
            p = d / f"arduino-cloud-credentials.{ext}"
            if p.is_file():
                text = p.read_text()
                c = json.loads(text) if ext == "json" else _parse_flat_yaml(text)
                return c.get("client", ""), c.get("secret", ""), c.get("organization", "")
    sys.exit("no Arduino Cloud credentials found (run `arduino-cloud-cli credentials init`)")


def get_token(client, secret):
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": client,
        "client_secret": secret, "audience": "https://api2.arduino.cc/iot",
    }).encode()
    req = urllib.request.Request(f"{BASE}/iot/v1/clients/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def call(method, path, body=None):
    client, secret, org = load_credentials()
    headers = {"Authorization": f"Bearer {get_token(client, secret)}",
               "Content-Type": "application/json"}
    if org:
        headers["X-Organization"] = org
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {method} {path}: {e.read().decode(errors='replace')[:1000]}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    body = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    json.dump(call(sys.argv[1].upper(), sys.argv[2], body), sys.stdout, indent=1)
    print()
