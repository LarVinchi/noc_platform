"""Generate a dummy fibre route KMZ around Lekki Phase 1, Lagos.

Coordinates are approximate and for prototype/demo purposes only.
Run:  python make_sample_kmz.py   ->  sample/lekki_phase1_demo.kmz
"""
import os
import zipfile
from xml.sax.saxutils import escape

OUT = os.path.join(os.path.dirname(__file__), "sample", "lekki_phase1_demo.kmz")

# (lon, lat)
NODES = {
    "POP":  ("Lekki Phase 1 POP", (3.4650, 6.4468), "pop", "live", "Main point of presence, 96-port ODF"),
    "J1":   ("JC-01 Admiralty / Fola Osibo", (3.4702, 6.4481), "closure", "live", "Splice closure, 48F"),
    "J2":   ("JC-02 Admiralty Mid", (3.4754, 6.4493), "closure", "live", "Splice closure, 48F"),
    "J3":   ("JC-03 Admiralty East", (3.4803, 6.4504), "closure", "live", "Splice closure, 24F"),
    "B1":   ("HH-11 Fola Osibo North", (3.4707, 6.4443), "handhole", "live", "Handhole"),
    "B2":   ("JC-04 Fola Osibo South", (3.4714, 6.4412), "closure", "live", "Splice closure, 24F"),
    "C1":   ("HH-21 Freedom Way North", (3.4762, 6.4456), "handhole", "live", "Handhole"),
    "C2":   ("JC-05 Freedom Way South", (3.4770, 6.4426), "closure", "live", "Splice closure, 24F"),
    "D1":   ("Lekki Business Hub (customer)", (3.4808, 6.4532), "customer", "live", "Enterprise customer, 1G DIA"),
    "FAULT": ("Fibre cut near Admiralty Mid", (3.4779, 6.4499), "fault", "down", "Backhoe damage reported, splice crew dispatched"),
}

# name, status, fibre count, cable type, ordered waypoints (lon, lat)
ROUTES = [
    ("Backbone A: POP to JC-01", "live", 96, "ADSS 96F",
     [NODES["POP"][1], (3.4668, 6.4472), (3.4685, 6.4477), NODES["J1"][1]]),
    ("Backbone B: JC-01 to JC-02", "live", 96, "ADSS 96F",
     [NODES["J1"][1], (3.4720, 6.4485), (3.4738, 6.4489), NODES["J2"][1]]),
    ("Backbone C: JC-02 to JC-03", "down", 48, "ADSS 48F",
     [NODES["J2"][1], (3.4768, 6.4496), NODES["FAULT"][1], (3.4790, 6.4501), NODES["J3"][1]]),
    ("Fola Osibo Rd North", "live", 48, "Underground 48F",
     [NODES["J1"][1], (3.4704, 6.4462), NODES["B1"][1]]),
    ("Fola Osibo Rd South", "live", 48, "Underground 48F",
     [NODES["B1"][1], (3.4710, 6.4428), NODES["B2"][1]]),
    ("Freedom Way North", "live", 48, "Underground 48F",
     [NODES["J2"][1], (3.4758, 6.4475), NODES["C1"][1]]),
    ("Freedom Way South", "down", 48, "Underground 48F",
     [NODES["C1"][1], (3.4766, 6.4441), NODES["C2"][1]]),
    ("Ring closure: Fola Osibo to Freedom Way", "live", 24, "ADSS 24F",
     [NODES["B2"][1], (3.4728, 6.4409), (3.4750, 6.4412), NODES["C2"][1]]),
    ("Customer drop: Lekki Business Hub", "live", 24, "ADSS 24F",
     [NODES["J3"][1], (3.4805, 6.4518), NODES["D1"][1]]),
]


def coord_str(points):
    return " ".join(f"{lon},{lat},0" for lon, lat in points)


def build_kml():
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             "<name>Lekki Phase 1 Fibre Network (Demo)</name>",
             "<description>Dummy test route for prototype use.</description>",
             '<Style id="live"><LineStyle><color>ffa6e62e</color><width>4</width></LineStyle></Style>',
             '<Style id="down"><LineStyle><color>ff4b4bff</color><width>4</width></LineStyle></Style>']

    parts.append("<Folder><name>Cable routes</name>")
    for name, status, fibres, cable, pts in ROUTES:
        parts.append(
            f"<Placemark><name>{escape(name)}</name><styleUrl>#{status}</styleUrl>"
            f'<ExtendedData><Data name="status"><value>{status}</value></Data>'
            f'<Data name="fibre_count"><value>{fibres}</value></Data>'
            f'<Data name="cable_type"><value>{escape(cable)}</value></Data></ExtendedData>'
            f"<LineString><tessellate>1</tessellate><coordinates>{coord_str(pts)}</coordinates></LineString>"
            "</Placemark>")
    parts.append("</Folder>")

    parts.append("<Folder><name>Sites and equipment</name>")
    for _, (name, pt, kind, status, desc) in NODES.items():
        parts.append(
            f"<Placemark><name>{escape(name)}</name><description>{escape(desc)}</description>"
            f'<ExtendedData><Data name="status"><value>{status}</value></Data>'
            f'<Data name="type"><value>{kind}</value></Data></ExtendedData>'
            f"<Point><coordinates>{pt[0]},{pt[1]},0</coordinates></Point></Placemark>")
    parts.append("</Folder></Document></kml>")
    return "\n".join(parts)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", build_kml())
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
