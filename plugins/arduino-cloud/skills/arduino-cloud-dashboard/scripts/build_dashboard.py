#!/usr/bin/env python3
"""Build (and optionally create) an Arduino Cloud dashboard from a compact spec.

The spec is a small JSON file that Claude writes from the user's request:

{
  "name": "Serra",                          # dashboard name (prefix added automatically)
  "things": {"serra": "Greenhouse"},        # alias -> Thing UUID or exact Thing name
  "pages": [{"id": "main", "name": "Overview", "icon": "dashboard_filled"}],   # optional
  "widgets": [
    {"type": "Gauge", "var": "serra:temperature", "name": "Temperatura",
     "options": {"min": 0, "max": 50}},
    {"type": "Advanced Chart", "vars": ["serra:temperature", "serra:humidity"]},
    {"type": "Sticky Note", "options": {"title": "Note", "content": "**hi**"}},
    {"type": "Switch", "var": "serra:pump", "size": [3, 3], "page": "main"},
    {"type": "Value", "var": "serra:co2", "pos": [0, 12]}           # explicit x,y (desktop)
  ]
}

Usage:
  build_dashboard.py spec.json                 # validate + write template, print summary
  build_dashboard.py spec.json --create        # ... and create it on Arduino Cloud
  build_dashboard.py spec.json --out t.json    # choose where the template goes

Only the Python standard library and `arduino-cloud-cli` are required.
"""

import argparse
import json
import os
import re
import subprocess
import sys

PREFIX = "🤖 Claude · "
CLI = os.environ.get("ARDUINO_CLOUD_CLI", "arduino-cloud-cli")
DESKTOP_COLS = 24
MOBILE_COLS = 8
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
CHART_COLORS = ["#0CA1A6", "#622998", "#2D65F4", "#EC4635", "#FE9B4F"]

# Variable type families used for compatibility checks.
BOOL = {"STATUS", "HOME_SWITCH", "HOME_SMART_PLUG", "HOME_CONTACT_SENSOR", "HOME_MOTION_SENSOR",
        "HOME_LIGHT"}
STRING = {"CHARSTRING"}
SPECIAL = BOOL | STRING | {
    "LOCATION", "COLOR_HSB", "COLOR_RGB", "TIME", "SCHEDULE", "GENERIC_COMPLEX_PROPERTY",
    "HOME_COLORED_LIGHT", "HOME_DIMMED_LIGHT", "HOME_TELEVISION"}
NUMERIC = "numeric"  # anything not in SPECIAL (INT, FLOAT, all unit types...)
ANY = "any"


def family_match(vtype, accepted):
    base = re.sub(r"^(GOOGLE_|SMART_)", "", vtype)
    for a in accepted:
        if a == ANY or a == base:
            return True
        if a == NUMERIC and base not in SPECIAL:
            return True
        if a == "bool" and base in BOOL:
            return True
    return False


# type -> accepted variable families, number of variables (min,max), desktop (w,h), mobile (w,h), default options
WIDGETS = {
    "Value":          (["numeric", "CHARSTRING", "bool"], (1, 1), (4, 3), (4, 3), {}),
    "Gauge":          ([NUMERIC], (1, 1), (6, 6), (4, 4), {"min": 0, "max": 100}),
    "Percentage":     ([NUMERIC], (1, 1), (5, 5), (4, 5), {"min": 0, "max": 100}),
    "Chart":          ([NUMERIC], (1, 1), (9, 6), (8, 6), {"interpolation": "spline"}),
    "Advanced Chart": ([NUMERIC], (1, 5), (10, 9), (8, 9),
                       {"multipleAxes": False, "showLegend": True, "showYAxes": True}),
    "Switch":         (["bool"], (1, 1), (3, 3), (4, 4), {"showLabels": True}),
    "Push Button":    (["bool"], (1, 1), (4, 4), (4, 4), {}),
    "LED":            (["bool"], (1, 1), (2, 2), (4, 2), {"mode": "Color 1"}),
    "Status":         (["bool"], (1, 1), (2, 2), (4, 2), {"mode": "On / Off"}),
    "Slider":         ([NUMERIC], (1, 1), (6, 4), (8, 4), {"min": 0, "max": 100}),
    "Stepper":        ([NUMERIC, "TIME"], (1, 1), (4, 3), (4, 3), {"min": 0, "max": 100, "step": 1}),
    "Value Selector": (["INT", "CHARSTRING", NUMERIC], (1, 1), (6, 3), (8, 3), {}),
    "Value Dropdown": (["INT", "CHARSTRING", NUMERIC], (1, 1), (5, 3), (8, 3), {}),
    "Messenger":      (["CHARSTRING"], (1, 1), (8, 12), (8, 10), {}),
    "Color":          (["COLOR_HSB", "COLOR_RGB"], (1, 1), (6, 7), (8, 7), {}),
    "Colored light":  (["HOME_COLORED_LIGHT"], (1, 1), (7, 8), (8, 7), {}),
    "Dimmed light":   (["HOME_DIMMED_LIGHT"], (1, 1), (7, 8), (8, 7), {}),
    "Map":            (["LOCATION"], (1, 1), (8, 8), (8, 8), {}),
    "Advanced Map":   (["LOCATION"], (1, 1), (10, 9), (8, 9),
                       {"markerType": "CONNECTED_DOTS", "markersColor": "#0CA1A6"}),
    "Time Picker":    (["TIME"], (1, 1), (7, 5), (8, 5),
                       {"display": "Date and Time", "dateFormat": "dd / MM / yyyy", "timeFormat": "HH : mm"}),
    "Scheduler":      (["SCHEDULE"], (1, 1), (10, 7), (8, 7),
                       {"display": "Date and Time", "dateFormat": "dd / MM / yyyy", "timeFormat": "HH : mm"}),
    "Image Map":      ([NUMERIC, "CHARSTRING", "bool"], (0, 20), (12, 10), (8, 9), {}),
    "Sticky Note":    ([], (0, 0), (6, 4), (8, 4),
                       {"title": "", "content": "", "color": "#FFEAA1", "visibility": "Title + Paragraph"}),
    "Link":           ([], (0, 0), (7, 4), (8, 4), {"showFullUrl": False}),
    "Image":          ([], (0, 0), (6, 6), (8, 6), {"fitting": "fit", "background": False}),
}
ALIASES = {k.lower(): k for k in WIDGETS}
ALIASES.update({"colored light": "Colored light", "dimmed light": "Dimmed light",
                "dropdown": "Value Dropdown", "selector": "Value Selector", "button": "Push Button",
                "note": "Sticky Note", "chart advanced": "Advanced Chart", "timepicker": "Time Picker"})


def die(msg):
    sys.exit(f"error: {msg}")


def cli_json(*args):
    r = subprocess.run([CLI, *args, "--format", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"`{CLI} {' '.join(args)}` failed: {r.stderr.strip() or r.stdout.strip()}")
    return json.loads(r.stdout)


def resolve_things(spec_things):
    """alias -> (uuid, {variable_name: (type, permission)})"""
    all_things = None
    out = {}
    for alias, ref in spec_things.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", alias):
            die(f"thing alias '{alias}' must match [A-Za-z0-9_-]+")
        if UUID_RE.match(ref):
            tid = ref
        else:
            if all_things is None:
                all_things = cli_json("thing", "list")
            hits = [t for t in all_things if t["name"] == ref] or \
                   [t for t in all_things if t["name"].lower() == ref.lower()]
            if len(hits) != 1:
                names = ", ".join(sorted(t["name"] for t in all_things))
                die(f"thing '{ref}' matched {len(hits)} things. Available: {names}")
            tid = hits[0]["id"]
        tpl = cli_json("thing", "extract", "--id", tid)
        out[alias] = (tid, {v["variable_name"]: (v["type"], v["permission"]) for v in tpl.get("variables") or []})
    return out


def parse_ref(ref, things):
    if ":" not in ref:
        if len(things) != 1:
            die(f"variable '{ref}' must be written as alias:variable_name")
        ref = f"{next(iter(things))}:{ref}"
    alias, var = ref.split(":", 1)
    if alias not in things:
        die(f"unknown thing alias '{alias}' in '{ref}'")
    vars_ = things[alias][1]
    if var not in vars_:
        die(f"thing '{alias}' has no variable '{var}'. Available: {', '.join(sorted(vars_))}")
    return alias, var, vars_[var]


def pack(items, cols, key_size, key_pos):
    """Skyline-pack widgets without an explicit position into a `cols`-wide grid, in spec
    order: each goes to the highest free spot (leftmost on ties), below explicit widgets."""
    placed = [it for it in items if it.get(key_pos)]
    floor = max((it[key_pos][1] + it[key_size][1] for it in placed), default=0)
    sky = [floor] * cols
    for it in items:
        if it.get(key_pos):
            continue
        w, h = it[key_size]
        w = min(w, cols)
        x = min(range(cols - w + 1), key=lambda c: (max(sky[c:c + w]), c))
        y = max(sky[x:x + w])
        sky[x:x + w] = [y + h] * w
        it[key_pos] = [x, y]
        it[key_size] = [w, h]


def note_height(opts, width):
    """Rows a Sticky Note needs to show its text at `width` columns (~7.5 chars per column,
    ~0.6 rows per text line, ~2 rows for the title)."""
    import math
    per_line = max(10, int(width * 7.5))
    text = str(opts.get("content", "")) if opts.get("visibility") != "Title Only" else ""
    lines = sum(math.ceil(len(par) / per_line) if par.strip() else 0.5 for par in text.split("\n"))
    title = 2 if opts.get("title") and opts.get("visibility") != "Paragraph Only" else 0
    return max(2, math.ceil(title + 0.6 * lines))


def widen(items, cols, key_size, key_pos):
    """Stretch widgets to the right into free cells (used for the narrow mobile grid)."""
    busy = set()
    for it in items:
        (x, y), (w, h) = it[key_pos], it[key_size]
        busy |= {(c, r) for c in range(x, x + w) for r in range(y, y + h)}
    for it in sorted(items, key=lambda i: (i[key_pos][1], i[key_pos][0])):
        if it.get("mpos_fixed"):
            continue
        (x, y), (w, h) = it[key_pos], it[key_size]
        while x + w < cols and not any((x + w, r) in busy for r in range(y, y + h)):
            busy |= {(x + w, r) for r in range(y, y + h)}
            w += 1
        it[key_size] = [w, h]


def build(spec, things, warnings):
    pages = spec.get("pages") or []
    page_ids = {p["id"] for p in pages}
    widgets = []
    for i, w in enumerate(spec.get("widgets") or []):
        wtype = ALIASES.get(str(w.get("type", "")).lower())
        if not wtype:
            die(f"widget #{i}: unknown type '{w.get('type')}'. Known: {', '.join(WIDGETS)}")
        accepted, (nmin, nmax), dsize, msize, defaults = WIDGETS[wtype]
        refs = w.get("vars") or ([w["var"]] if w.get("var") else [])
        if not nmin <= len(refs) <= nmax:
            die(f"widget #{i} ({wtype}): needs {nmin}..{nmax} variables, got {len(refs)}")
        variables, keys = [], []
        for ref in refs:
            alias, var, (vtype, perm) = parse_ref(ref, things)
            if accepted and not family_match(vtype, accepted):
                warnings.append(f"{wtype} '{w.get('name', var)}': variable {alias}:{var} is {vtype}, "
                                f"usually expects {'/'.join(accepted)}")
            if wtype in ("Switch", "Push Button", "Slider", "Stepper", "Value Selector", "Value Dropdown",
                         "Color", "Colored light", "Dimmed light", "Time Picker", "Scheduler") and perm == "READ_ONLY":
                die(f"{wtype} on READ_ONLY variable {alias}:{var}: the UI shows it as an error widget. "
                    "Use a monitoring widget (Value/LED/Status/...) or a READ_WRITE variable")
            variables.append({"thing_id": alias, "variable_id": var})
            keys.append(f"{alias}:{var}")

        name = w.get("name") or (refs[0].split(":")[-1] if refs else wtype)
        opts = {**defaults, **(w.get("options") or {})}

        if wtype == "Advanced Chart":
            agg = opts.pop("aggregation_all", "AVG")
            opts.setdefault("aggregation", {k: {"value": agg} for k in keys})
            opts.setdefault("format", {k: {"color": {"color": CHART_COLORS[j % len(CHART_COLORS)]},
                                           "type": {"label": "Line", "value": "line"}} for j, k in enumerate(keys)})
            opts.setdefault("axes", {k: {"label": ""} for k in keys})
        if wtype in ("Value Selector", "Value Dropdown"):
            vals = opts.get("values")
            if not vals:
                die(f"widget #{i} ({wtype}): options.values is required, e.g. "
                    '[{"label": "OFF", "value": "0"}, {"label": "ON", "value": "1"}]')
            opts["values"] = [{"label": str(v["label"]), "value": str(v["value"])} for v in vals]
            if len({v["value"] for v in opts["values"]}) != len(opts["values"]):
                die(f"widget #{i} ({wtype}): duplicated values")
        if wtype == "Link" and not str(opts.get("url", "")).startswith("https://"):
            die(f"widget #{i} (Link): options.url must start with https://")
        if wtype == "Image" and "image" not in opts:
            if not opts.get("url"):
                die(f"widget #{i} (Image): options.url (https) is required")
            opts["image"] = {"source": "url", "url": opts.pop("url"),
                             **({"autoRefresh": opts.pop("autoRefresh")} if "autoRefresh" in opts else {})}
        if wtype == "Image Map" and "image" not in opts:
            die(f"widget #{i} (Image Map): options.image is required (see references/widgets.md)")

        page = w.get("page")
        if page and page not in page_ids:
            die(f"widget #{i}: unknown page '{page}'")
        if wtype == "Sticky Note":
            if not w.get("size"):
                dsize = (dsize[0], max(dsize[1], note_height(opts, dsize[0])))
            elif note_height(opts, w["size"][0]) > w["size"][1]:
                warnings.append(f"Sticky Note '{name}': text probably overflows {w['size']}; "
                                f"needs ~{note_height(opts, w['size'][0])} rows")
            if not w.get("size_mobile"):
                msize = (MOBILE_COLS, note_height(opts, MOBILE_COLS))
        widgets.append({
            "type": wtype, "name": name, "variables": variables, "options": opts,
            "page_id": page or (pages[0]["id"] if pages else "0"),
            "size": list(w.get("size") or dsize), "pos": w.get("pos"),
            "msize": list(w.get("size_mobile") or msize), "mpos": w.get("pos_mobile"),
            "mpos_fixed": bool(w.get("pos_mobile") or w.get("size_mobile")),
        })

    # Layout per page, preserving spec order.
    for pid in {w["page_id"] for w in widgets}:
        group = [w for w in widgets if w["page_id"] == pid]
        pack(group, DESKTOP_COLS, "size", "pos")
        pack(group, MOBILE_COLS, "msize", "mpos")
        widen(group, MOBILE_COLS, "msize", "mpos")

    out_widgets = []
    for w in widgets:
        o = {"type": w["type"], "name": w["name"],
             "width": w["size"][0], "height": w["size"][1], "x": w["pos"][0], "y": w["pos"][1],
             "width_mobile": w["msize"][0], "height_mobile": w["msize"][1],
             "x_mobile": w["mpos"][0], "y_mobile": w["mpos"][1],
             "options": w["options"]}
        if w["variables"]:
            o["variables"] = w["variables"]
        if w["page_id"] != "0":
            o["page_id"] = w["page_id"]
        out_widgets.append(o)

    name = spec.get("name") or die("spec.name is required")
    if not name.startswith(PREFIX):
        name = PREFIX + name
    tpl = {"name": name, "widgets": out_widgets}
    if pages:
        tpl["pages"] = [{"id": p["id"], "name": p["name"], "position": p.get("position", n),
                         **({"icon": p["icon"]} if p.get("icon") else {})} for n, p in enumerate(pages)]
    return tpl


def preview(tpl, mobile=False):
    """Per-page table plus an ASCII map of the grid (one char per cell, letter per widget)."""
    cols = MOBILE_COLS if mobile else DESKTOP_COLS
    sfx = "_mobile" if mobile else ""
    pages = {p["id"]: p["name"] for p in tpl.get("pages") or []} or {"0": "main"}
    lines = []
    for pid, pname in pages.items():
        ws = [w for w in tpl["widgets"] if w.get("page_id", "0") == pid]
        if not ws:
            continue
        height = max(w["y" + sfx] + w["height" + sfx] for w in ws)
        grid = [["." for _ in range(cols)] for _ in range(height)]
        lines.append(f"-- page '{pname}' ({'mobile' if mobile else 'desktop'}, {cols} cols) --")
        for n, w in enumerate(ws):
            ch = chr(ord("A") + n % 26) if n < 26 else chr(ord("a") + (n - 26) % 26)
            x, y, wd, h = w["x" + sfx], w["y" + sfx], w["width" + sfx], w["height" + sfx]
            for r in range(y, y + h):
                for c in range(x, min(x + wd, cols)):
                    grid[r][c] = "#" if grid[r][c] != "." else ch
            vs = ",".join(v["variable_id"] for v in w.get("variables") or [])
            lines.append(f"  {ch} {w['type']:<15} {w['name'][:28]:<28} {vs[:30]:<30} x={x} y={y} {wd}x{h}")
        lines += ["  |" + "".join(row) + "|" for row in grid]
        empty = sum(row.count(".") for row in grid)
        if empty:
            lines.append(f"  ({empty} empty cells; '#' = overlap)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", help="template output path (default: <spec>.template.json)")
    ap.add_argument("--create", action="store_true", help="create the dashboard on Arduino Cloud")
    ap.add_argument("--strict", action="store_true", help="treat compatibility warnings as errors")
    ap.add_argument("--mobile-preview", action="store_true", help="also print the mobile layout")
    a = ap.parse_args()

    spec = json.load(open(a.spec))
    things = resolve_things(spec.get("things") or {})
    warnings = []
    tpl = build(spec, things, warnings)

    out = a.out or re.sub(r"(\.json)?$", ".template.json", a.spec, count=1)
    with open(out, "w") as f:
        json.dump(tpl, f, indent=2, ensure_ascii=False)

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if warnings and a.strict:
        die("aborting because of --strict")

    override = ",".join(f"{alias}={tid}" for alias, (tid, _) in things.items())
    print(f"template: {out}  ({len(tpl['widgets'])} widgets, name '{tpl['name']}')")
    print(preview(tpl))
    if a.mobile_preview:
        print(preview(tpl, mobile=True))
    cmd = [CLI, "dashboard", "create", "--template", os.path.abspath(out), "--format", "json"]
    if override:
        cmd += ["--override", override]
    if not a.create:
        print("dry run; to create:\n  " + " ".join(f"'{c}'" if " " in c else c for c in cmd))
        return
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"dashboard create failed: {r.stderr.strip() or r.stdout.strip()}")
    info = json.loads(r.stdout)
    print(json.dumps({"id": info["id"], "name": info["name"],
                      "url": f"https://app.arduino.cc/dashboards/{info['id']}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
