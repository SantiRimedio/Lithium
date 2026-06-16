"""Generate a self-contained Leaflet explorer for bofedales_v2.

Renders accepted (green) + disputed (orange) bofedal polygons over an
OSM/satellite basemap with popups showing bofedal_id, area, and
reference overlap. Writes a single HTML file with all GeoJSON inlined.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd


REPO = Path(__file__).resolve().parents[1]
ACCEPTED = REPO / "Data" / "bofedales_v2.geojson"
DISPUTED = REPO / "Data" / "bofedales_v2_disputed.geojson"
BASINS = REPO / "Data" / "Endorheic_basins_Puna.geojson"
OUT = REPO / "output" / "bofedales_v2_explorer.html"


def _enrich(path: Path) -> dict:
    gdf = gpd.read_file(path).to_crs("EPSG:4326")
    gdf["area_m2"] = gdf.to_crs("EPSG:32719").geometry.area.round(0)
    return json.loads(gdf.to_json())


def main() -> None:
    accepted = _enrich(ACCEPTED)
    disputed = _enrich(DISPUTED)
    basins = json.loads(gpd.read_file(BASINS).to_crs("EPSG:4326").to_json())

    n_a = len(accepted["features"])
    n_d = len(disputed["features"])
    area_a = sum(f["properties"]["area_m2"] for f in accepted["features"]) / 1e6
    area_d = sum(f["properties"]["area_m2"] for f in disputed["features"]) / 1e6

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Bofedales v2 — Argentine Puna</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
  #legend {{
    position: absolute; bottom: 16px; left: 16px; z-index: 1000;
    background: rgba(255,255,255,.92); padding: 10px 14px;
    border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.2);
    font: 13px -apple-system, BlinkMacSystemFont, sans-serif; color: #222;
    line-height: 1.5;
  }}
  #legend .sw {{ display: inline-block; width: 14px; height: 14px;
    margin-right: 6px; vertical-align: -2px; border: 1px solid #555; }}
  #legend h4 {{ margin: 0 0 4px 0; font-size: 13px; }}
  .leaflet-popup-content {{ font: 12px monospace; }}
</style>
</head>
<body>
<div id="map"></div>
<div id="legend">
  <h4>Bofedales v2 — Argentine Puna</h4>
  <span class="sw" style="background:#2ca02c;opacity:.7"></span>
  Accepted: <b>{n_a}</b> polygons, ~{area_a:.1f} km²<br>
  <span class="sw" style="background:#ff7f0e;opacity:.7"></span>
  Disputed: <b>{n_d}</b> polygons, ~{area_d:.1f} km²<br>
  <span class="sw" style="background:transparent;border:1px solid #555"></span>
  Endorheic basins
</div>
<script>
const accepted = {json.dumps(accepted)};
const disputed = {json.dumps(disputed)};
const basins = {json.dumps(basins)};

const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{maxZoom: 19, attribution: '© OpenStreetMap'}});
const sat = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{maxZoom: 19, attribution: 'Tiles © Esri'}});

const map = L.map('map', {{
  center: [-24.5, -67.0], zoom: 7, layers: [sat]
}});

function popup(f) {{
  const p = f.properties;
  const haPerM2 = 1e-4;
  return `<b>${{p.bofedal_id || ''}}</b><br>` +
    `area: ${{(p.area_m2 || 0).toLocaleString()}} m² ` +
    `(${{((p.area_m2 || 0) * haPerM2).toFixed(2)}} ha)<br>` +
    (p.overlap_with_reference != null
      ? `reference overlap: ${{p.overlap_with_reference.toFixed(2)}}<br>` : '');
}}

const basinsLayer = L.geoJSON(basins, {{
  style: {{ color: '#555', weight: 1, fillOpacity: 0, dashArray: '3,3' }},
  interactive: false,
}}).addTo(map);

const acceptedLayer = L.geoJSON(accepted, {{
  style: {{ color: '#1b6e1b', weight: 1, fillColor: '#2ca02c', fillOpacity: 0.55 }},
  onEachFeature: (f, l) => l.bindPopup(popup(f)),
}}).addTo(map);

const disputedLayer = L.geoJSON(disputed, {{
  style: {{ color: '#a85508', weight: 1, fillColor: '#ff7f0e', fillOpacity: 0.45 }},
  onEachFeature: (f, l) => l.bindPopup(popup(f)),
}}).addTo(map);

L.control.layers(
  {{ "Satellite (ESRI)": sat, "OpenStreetMap": osm }},
  {{ "Accepted bofedales": acceptedLayer,
     "Disputed bofedales": disputedLayer,
     "Endorheic basins": basinsLayer }}
).addTo(map);

// Auto-fit to accepted polygons (with basins as fallback if none).
const fitTarget = acceptedLayer.getLayers().length ? acceptedLayer : basinsLayer;
map.fitBounds(fitTarget.getBounds(), {{padding: [40, 40]}});
</script>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
