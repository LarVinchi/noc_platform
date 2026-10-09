"""Read a .kmz (zipped KML) or .kml file and turn it into GeoJSON-style data
that the web map can draw, including live/down status and route length."""

import io
import math
import re
import zipfile
import xml.etree.ElementTree as ET

STATUS_LIVE = "live"
STATUS_DOWN = "down"
STATUS_UNKNOWN = "unknown"
STATUS_PLANNED = "planned"


def _strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _children(el, name):
    return [c for c in el if _strip_ns(c.tag) == name]


def _child_text(el, name, default=""):
    for c in el:
        if _strip_ns(c.tag) == name:
            return (c.text or "").strip()
    return default


def _find_all(el, name):
    return [e for e in el.iter() if _strip_ns(e.tag) == name]


def haversine_m(a, b):
    """Distance in metres between two (lon, lat) points."""
    r = 6371008.8
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(d))


def line_length_m(coords):
    return sum(haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def parse_coords(text):
    """KML coordinates are 'lon,lat[,alt]' separated by whitespace."""
    out = []
    for chunk in re.split(r"\s+", (text or "").strip()):
        if not chunk:
            continue
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
            if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90:
                out.append([lon, lat])
        except ValueError:
            continue
    return out


def _normalise_status(value):
    if re.search(r"\b(down|cut|fault|outage|offline|los)\b|#down", value):
        return STATUS_DOWN
    if re.search(r"\b(planned|proposed|future|tbc|new build|under construction|to be built|to be constructed)\b|#planned", value):
        return STATUS_PLANNED
    if re.search(r"\b(live|up|active|online|ok|completed|commissioned|in service|as-built)\b|#live", value):
        return STATUS_LIVE
    return STATUS_UNKNOWN


def detect_status(placemark, ctx=None):
    """Return (status, source). source is 'file' (explicit status field),
    'inferred' (guessed from names, styles or schema) or 'none'."""
    for el in placemark.iter():
        tag = _strip_ns(el.tag)
        if tag in ("Data", "SimpleData") and (el.get("name") or "").lower() == "status":
            value = (_child_text(el, "value") if tag == "Data" else (el.text or "")).strip().lower()
            if value:
                s = _normalise_status(value)
                if s != STATUS_UNKNOWN:
                    return s, "file"
    ed = _extended_data(placemark)
    sources = [ed.get("Route_Name", ""), _child_text(placemark, "name"), _child_text(placemark, "description"),
               _child_text(placemark, "styleUrl")]
    if ctx:
        sources.append(ctx["schemas"].get(_schema_id(placemark), ""))
    for source in sources:
        s = _normalise_status(source.lower().replace("_", " "))
        if s != STATUS_UNKNOWN:
            return s, "inferred"
    return STATUS_UNKNOWN, "none"


def _schema_id(placemark):
    for el in placemark.iter():
        if _strip_ns(el.tag) == "SchemaData":
            return (el.get("schemaUrl") or "").lstrip("#")
    return ""


def kml_color_to_hex(c):
    """KML colours are aabbggrr."""
    c = (c or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{8}", c):
        return "#" + c[6:8] + c[4:6] + c[2:4]
    return None


def build_context(root):
    """Collect schema names and resolved line styles (following StyleMap -> Style)."""
    schemas, styles, maps = {}, {}, {}
    for el in root.iter():
        tag = _strip_ns(el.tag)
        if tag == "Schema" and el.get("id"):
            schemas[el.get("id")] = el.get("name") or ""
        elif tag == "Style" and el.get("id"):
            ls = next(iter(_children(el, "LineStyle")), None)
            if ls is not None:
                w = _child_text(ls, "width")
                styles[el.get("id")] = {"color": kml_color_to_hex(_child_text(ls, "color")),
                                        "width": float(w) if re.fullmatch(r"[\d.]+", w or "") else None}
        elif tag == "StyleMap" and el.get("id"):
            for pair in _children(el, "Pair"):
                if _child_text(pair, "key") == "normal":
                    maps[el.get("id")] = _child_text(pair, "styleUrl").lstrip("#")
    return {"schemas": schemas, "styles": styles, "maps": maps}


def resolve_line_style(placemark, ctx):
    sid = _child_text(placemark, "styleUrl").lstrip("#")
    seen = 0
    while sid in ctx["maps"] and seen < 5:
        sid, seen = ctx["maps"][sid], seen + 1
    return ctx["styles"].get(sid, {})


def humanise(s):
    s = re.sub(r"[_\-]+", " ", s or "").strip()
    return (s[:1].upper() + s[1:]).replace("Dwdm", "DWDM").replace("dwdm", "DWDM")


def infer_node_type(name, style_url="", data=None):
    t = ((data or {}).get("type") or "").lower()
    if t:
        return t
    n = (name or "").lower()
    if re.search(r"\b(cls|cable landing|landing station)\b", n):
        return "cls"
    if re.search(r"\bpop\b|point of presence", n):
        return "pop"
    if re.search(r"\b(jc|closure|splice|joint)\b", n):
        return "closure"
    if re.search(r"\b(hh|handhole|manhole|chamber)\b", n):
        return "handhole"
    return ""


def _extended_data(placemark):
    data = {}
    for el in placemark.iter():
        tag = _strip_ns(el.tag)
        if tag == "Data" and el.get("name"):
            data[el.get("name")] = _child_text(el, "value")
        elif tag == "SimpleData" and el.get("name"):
            data[el.get("name")] = (el.text or "").strip()
    return data


def read_kml_bytes(raw, filename=""):
    """Return KML bytes from a .kmz (zip) or plain .kml upload."""
    if zipfile.is_zipfile(io.BytesIO(raw)):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".kml")]
            if not names:
                raise ValueError("No .kml file found inside the KMZ archive.")
            main = "doc.kml" if "doc.kml" in names else names[0]
            if len(z.infolist()) > 512 or z.getinfo(main).file_size > 50 * 1024 * 1024:
                raise ValueError("KMZ contents exceed supported limits.")
            return z.read(main)
    if filename.lower().endswith(".kmz"):
        raise ValueError("This file has a .kmz extension but is not a valid zip archive.")
    return raw


def _recorded_km(data):
    for key, scale in (("Dist_Km", 1.0), ("New_Dist_m", 0.001), ("Distance_km", 1.0), ("Length_km", 1.0)):
        v = data.get(key)
        try:
            if v not in (None, ""):
                return round(float(v) * scale, 3)
        except ValueError:
            pass
    return None


def _display_name(raw):
    return re.sub(r"\.(kmz|kml)$", "", raw or "", flags=re.I).strip()


def parse_kmz(raw, filename=""):
    kml = read_kml_bytes(raw, filename)
    try:
        root = ET.fromstring(kml)
    except ET.ParseError as e:
        raise ValueError(f"The KML inside the file is not valid XML: {e}")

    ctx = build_context(root)
    doc_name = ""
    for el in root.iter():
        if _strip_ns(el.tag) in ("Document", "Folder") and _child_text(el, "name"):
            doc_name = _child_text(el, "name")
            break

    features = []
    name_counts = {}
    for pm in _find_all(root, "Placemark"):
        data = _extended_data(pm)
        raw_name = _child_text(pm, "name")
        desc = re.sub(r"<[^>]+>", "", _child_text(pm, "description"))
        status, source = detect_status(pm, ctx)
        style = resolve_line_style(pm, ctx)
        has_line = bool(_find_all(pm, "LineString"))

        if raw_name:
            name = raw_name
        elif data.get("Route_Name"):
            name = data["Route_Name"]
        elif has_line:
            base = humanise(ctx["schemas"].get(_schema_id(pm), "")) or "Route"
            name_counts[base] = name_counts.get(base, 0) + 1
            name = f"{base} {name_counts[base]}"
        else:
            name = "Unnamed site"

        props = {"name": name, "description": desc, "status": status, "status_source": source,
                 "data": data, "recorded_km": _recorded_km(data),
                 "kml_color": style.get("color"), "kml_width": style.get("width")}

        for ls in _find_all(pm, "LineString"):
            coords = parse_coords(_child_text(ls, "coordinates"))
            if len(coords) >= 2:
                features.append({"type": "Feature",
                                 "properties": {**props, "kind": "route", "length_m": round(line_length_m(coords), 1)},
                                 "geometry": {"type": "LineString", "coordinates": coords}})
        for pt in _find_all(pm, "Point"):
            coords = parse_coords(_child_text(pt, "coordinates"))
            if coords:
                features.append({"type": "Feature",
                                 "properties": {**props, "kind": "node",
                                                "node_type": infer_node_type(name, "", data)},
                                 "geometry": {"type": "Point", "coordinates": coords[0]}})

    if not features:
        raise ValueError("No routes or points were found in this file.")

    return {"type": "FeatureCollection", "name": _display_name(doc_name or filename) or "Fibre network",
            "features": features, "summary": summarise(features)}


def summarise(features):
    routes = [f for f in features if f["properties"]["kind"] == "route"]
    nodes = [f for f in features if f["properties"]["kind"] == "node"]
    keys = (STATUS_LIVE, STATUS_DOWN, STATUS_PLANNED, STATUS_UNKNOWN)
    total = {s: 0.0 for s in keys}
    count = {s: 0 for s in keys}
    for f in routes:
        s = f["properties"]["status"]
        total[s] += f["properties"]["length_m"]
        count[s] += 1
    out = {"routes": len(routes), "nodes": len(nodes), "length_m": round(sum(total.values()), 1)}
    for s in keys:
        out[f"{s}_m"] = round(total[s], 1)
        out[f"{s}_count"] = count[s]
    return out
