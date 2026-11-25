"""Build a compact chargers.json from the Swiss federal open data (BFE / ich-tanke-strom.ch)."""
import argparse
import gzip
import html
import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

BASE = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet"
OICP_URL = f"{BASE}/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
# Prices and the station grouping only exist in the HTML popups of the GeoJSON layer.
GEOJSON_URL = f"{BASE}/data/ch.bfe.ladestellen-elektromobilitaet_en.json"
NO_PRICE = "Please consult your provider"

PLUGS = {
    "Type 2 Outlet": "Type 2",
    "Type 2 Connector (Cable Attached)": "Type 2 cable",
    "Type 1 Connector (Cable Attached)": "Type 1",
    "CCS Combo 2 Plug (Cable Attached)": "CCS",
    "CCS Combo 1 Plug (Cable Attached)": "CCS1",
    "CHAdeMO": "CHAdeMO",
    "Tesla Connector": "Tesla",
    "Type J Swiss Standard": "Type 13",
}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ev-charge-scout", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def power_kw(f):
    try:
        p = float(f.get("power") or 0)
    except ValueError:
        p = 0
    if p <= 0:
        v, a = float(f.get("Voltage") or 0), float(f.get("Amperage") or 0)
        p = v * a * (3 if f.get("powertype") == "AC_3_PHASE" else 1) / 1000
    return round(p, 1) if p > 0 else None


def current_type(f, plug):
    t = f.get("powertype")
    if t:
        return "DC" if t == "DC" else "AC"
    return "DC" if plug in ("CCS", "CCS1", "CHAdeMO") else "AC"


def station_name(r):
    raw = r.get("ChargingStationNames") or []
    names = {n.get("lang"): n["value"] for n in (raw if isinstance(raw, list) else [raw]) if n.get("value")}
    return names.get("de") or names.get("en") or next(iter(names.values()), "")


def address(r):
    a = r.get("Address") or {}
    street = str(a.get("Street") or "").strip()
    city = " ".join(str(x) for x in (a.get("PostalCode"), a.get("City")) if x)
    return ", ".join(x for x in (street, city) if x)


def popup_text(desc):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc))).strip()


def build(oicp, geo):
    evses = {}
    for op in oicp["EVSEData"]:
        for r in op["EVSEDataRecord"]:
            r["_op"] = op.get("OperatorName") or ""
            evses[r["EvseID"]] = r

    groups, prices = [], {}
    for feat in geo["features"]:
        desc = feat["properties"].get("description", "")
        m = re.search(r"stationids=([^\"&]+)", desc)
        ids = [i for i in (m.group(1).split(",") if m else [feat["id"]]) if i in evses]
        if not ids:
            continue
        p = re.search(r" Price (.*?) Access ", popup_text(desc) + " Access ")
        price = p.group(1).strip() if p and not p.group(1).startswith(NO_PRICE) else None
        groups.append(ids)
        for i in ids:
            prices[i] = price
    grouped = {i for g in groups for i in g}
    groups += [[i] for i in evses if i not in grouped]

    stations = []
    for ids in groups:
        first = evses[ids[0]]
        lat, lon = (float(x) for x in first["GeoCoordinates"]["Google"].split())
        points = defaultdict(list)
        for i in ids:
            r = evses[i]
            plug = PLUGS.get((r.get("Plugs") or [""])[0], (r.get("Plugs") or ["?"])[0])
            facs = r.get("ChargingFacilities") or [{}]
            best = max(facs, key=lambda f: power_kw(f) or 0)
            points[(power_kw(best), current_type(best, plug), plug)].append(i)
        stations.append({
            "lat": round(lat, 6), "lon": round(lon, 6),
            "name": station_name(first), "addr": address(first), "op": first["_op"],
            "access": first.get("Accessibility"), "open24": first.get("IsOpen24Hours"),
            "price": next((prices[i] for i in ids if prices.get(i)), None),
            "points": [{"kw": k[0], "type": k[1], "plug": k[2], "ids": v} for k, v in points.items()],
        })
    return stations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site/chargers.json")
    args = ap.parse_args()
    stations = build(get_json(OICP_URL), get_json(GEOJSON_URL))
    out = {"meta": {"fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source": "BFE / ich-tanke-strom.ch (data.geo.admin.ch)"},
           "stations": stations}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    n_evse = sum(len(p["ids"]) for s in stations for p in s["points"])
    n_price = sum(1 for s in stations if s["price"])
    print(f"{len(stations)} stations, {n_evse} charge points, {n_price} with price -> {args.out}")


if __name__ == "__main__":
    main()
