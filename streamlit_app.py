import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import polyline
import random

st.set_page_config(page_title="Peta Cantik", page_icon="🗺️", layout="wide")

st.title('🗺️ Peta Cantik')
st.write('Interactive retro-style map — powered by OpenStreetMap.')

# ── helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def geocode(query):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "PetaCantik/1.0"}, timeout=8)
        d = r.json()
        if d:
            return float(d[0]["lat"]), float(d[0]["lon"]), d[0].get("display_name","")
    except Exception:
        pass
    return None, None, None

@st.cache_data(show_spinner=False)
def overpass_buildings(lat, lon, radius):
    q = f"""[out:json][timeout:25];
    (way["building"](around:{radius},{lat},{lon});
     relation["building"](around:{radius},{lat},{lon}););
    out body; >; out skel qt;"""
    try:
        r = requests.post("https://overpass-api.de/api/interpreter",
                          data={"data": q}, timeout=25)
        return r.json().get("elements", [])
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def overpass_pois(lat, lon, radius, amenity):
    q = f"""[out:json][timeout:20];
    node["amenity"="{amenity}"](around:{radius},{lat},{lon});
    out body;"""
    try:
        r = requests.post("https://overpass-api.de/api/interpreter",
                          data={"data": q}, timeout=20)
        return r.json().get("elements", [])
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def osrm_route(coords):
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    try:
        r = requests.get(
            f"https://router.project-osrm.org/route/v1/driving/{coord_str}",
            params={"overview":"full","geometries":"polyline"}, timeout=10)
        d = r.json()
        if d.get("code") == "Ok":
            route = d["routes"][0]
            return (polyline.decode(route["geometry"]),
                    round(route["distance"]/1000, 2),
                    round(route["duration"]/60, 1))
    except Exception:
        pass
    return None, None, None

PALETTE = ["#f5e6a3","#f0c070","#f0a040","#e06820","#c83010","#a01808"]
BTYPE_COLOR = {
    "residential": PALETTE[1], "house": PALETTE[1],
    "apartments":  PALETTE[2], "school": PALETTE[2],
    "commercial":  PALETTE[3], "office": PALETTE[3],
    "retail":      PALETTE[4], "hotel": PALETTE[4],
    "hospital":    PALETTE[5], "church": PALETTE[5],
    "industrial":  PALETTE[0],
}
def bld_color(tags):
    return BTYPE_COLOR.get(tags.get("building","yes"), PALETTE[random.randint(0,2)])

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    mode = st.selectbox("Map Mode", [
        "🎨 Retro City Map",
        "📍 Marker Map",
        "🌍 Choropleth Map",
        "🛣️ Route Planner",
        "🔍 POI Explorer",
    ])
    zoom = st.slider("Default Zoom", 2, 18, 14)
    tile = st.selectbox("Map Layer", {
        "CartoDB Positron":  "CartoDB positron",
        "CartoDB Dark":     "CartoDB dark_matter",
        "OpenStreetMap":     "OpenStreetMap",
    }.keys())
    TILES = {
        "CartoDB Positron":  "CartoDB positron",
        "CartoDB Dark":     "CartoDB dark_matter",
        "OpenStreetMap":     "OpenStreetMap",
    }
    tile_layer = TILES[tile]
    st.info("Data: OpenStreetMap · Routing: OSRM · Geocoding: Nominatim")

st.divider()

# ════════════════════════════════════════════════════════════════════════════════
# 🎨  RETRO BANDAR
# ════════════════════════════════════════════════════════════════════════════════
if mode == "🎨 Retro City Map":
    st.subheader("🎨 Retro City Map")
    st.caption("OSM buildings painted with a warm retro palette — cream, orange, red.")

    col1, col2 = st.columns([1, 2.5])
    with col1:
        st.markdown("**📍 Centre Coordinates**")
        lat = st.number_input("Latitude", value=3.1390, format="%.6f", key="retro_lat")
        lon = st.number_input("Longitude", value=101.6869, format="%.6f", key="retro_lon")
        rad   = st.slider("Radius (m)", 100, 1200, 400, 50)
        tips  = st.checkbox("Show building tooltips", True)
        st.markdown("**Colour palette**")
        legend = [("#f5e6a3","Industrialal"),("#f0c070","Residential"),
                  ("#f0a040","Apartments"),("#e06820","Commercial"),
                  ("#c83010","Retail / Hotel"),("#a01808","Hospital / Church")]
        for hx, lb in legend:
            st.markdown(
                f'<span style="background:{hx};padding:2px 10px;border-radius:3px;'
                f'border:1px solid #888;margin-right:6px;font-size:.8rem">&nbsp;</span>{lb}',
                unsafe_allow_html=True)

    with col2:
        with st.spinner("Fetching buildings from Overpass…"):
            elems = overpass_buildings(lat, lon, rad)

        nodes = {e["id"]:(e["lat"],e["lon"]) for e in elems if e["type"]=="node"}
        ways  = [e for e in elems if e["type"]=="way" and "nodes" in e]

        m = folium.Map(location=[lat,lon], zoom_start=zoom, tiles="CartoDB positron")

        # sepia CSS on tile layer
        folium.Element("""<style>
          .leaflet-tile-pane{filter:sepia(.4) saturate(.75) brightness(1.05);}
          .leaflet-container{background:#a8d4e6;}
        </style>""").add_to(m.get_root().html)

        count = 0
        for way in ways:
            pts = [nodes[n] for n in way.get("nodes",[]) if n in nodes]
            if len(pts) < 3: continue
            tags = way.get("tags",{})
            folium.Polygon(pts, color="#1a1209", weight=0.8,
                fill=True, fill_color=bld_color(tags), fill_opacity=0.9,
                tooltip=tags.get("building","building") if tips else None,
            ).add_to(m)
            count += 1

        folium.CircleMarker([lat,lon], radius=5, color="#1a1209",
            fill=True, fill_color="#d29922", fill_opacity=1).add_to(m)

        st_folium(m, width="100%", height=560)
        st.markdown(f"**{count}** buildings rendered · radius **{rad}m** · `{lat:.4f}, {lon:.4f}`")

# ════════════════════════════════════════════════════════════════════════════════
# 📍  MARKER MAP
# ════════════════════════════════════════════════════════════════════════════════
elif mode == "📍 Marker Map":
    st.subheader("📍 Marker Map")
    st.caption("Enter coordinates, place names, or upload a CSV.")

    col1, col2 = st.columns([1, 2])
    with col1:
        method = st.radio("Input Method", ["Manual Coordinates","Place Name","Upload CSV"])
        markers = []

        if method == "Manual Coordinates":
            n = st.number_input("Number of points", 1, 10, 3)
            for i in range(int(n)):
                a, b, c = st.columns([2,2,3])
                lt = a.number_input(f"Lat {i+1}", value=3.139+i*0.02, format="%.4f", key=f"la{i}")
                ln = b.number_input(f"Lon {i+1}", value=101.687+i*0.02, format="%.4f", key=f"lo{i}")
                lb = c.text_input(f"Label {i+1}", value=f"Point {i+1}", key=f"lb{i}")
                markers.append({"lat":lt,"lon":ln,"label":lb})

        elif method == "Place Name":
            raw = st.text_area("Place names (one per line)", "Kuala Lumpur\nPetronas Twin Towers\nBatu Caves", height=110)
            for p in [l.strip() for l in raw.splitlines() if l.strip()]:
                lt, ln, _ = geocode(p)
                if lt: markers.append({"lat":lt,"lon":ln,"label":p})

        else:
            f = st.file_uploader("CSV (lat, lon, label)", type="csv")
            if f:
                df = pd.read_csv(f)
                if "lat" in df.columns and "lon" in df.columns:
                    lc = "label" if "label" in df.columns else df.columns[0]
                    for _, row in df.iterrows():
                        markers.append({"lat":row["lat"],"lon":row["lon"],"label":str(row.get(lc,""))})

        color   = st.color_picker("Marker colour", "#e06820")
        cluster = st.checkbox("Clustering", True)

    with col2:
        clat = sum(x["lat"] for x in markers)/len(markers) if markers else 3.139
        clon = sum(x["lon"] for x in markers)/len(markers) if markers else 101.687
        m = folium.Map(location=[clat,clon], zoom_start=zoom, tiles=tile_layer)
        if cluster:
            from folium.plugins import MarkerCluster
            tgt = MarkerCluster().add_to(m)
        else:
            tgt = m
        for mk in markers:
            folium.CircleMarker([mk["lat"],mk["lon"]], radius=8, color=color,
                fill=True, fill_color=color, fill_opacity=0.85,
                tooltip=mk["label"],
                popup=folium.Popup(f"<b>{mk['label']}</b><br>{mk['lat']:.4f}, {mk['lon']:.4f}", max_width=200),
            ).add_to(tgt)
        st_folium(m, width="100%", height=520)
        if markers:
            c1,c2,c3 = st.columns(3)
            c1.metric("Markers", len(markers))
            c2.metric("Lat span", f"{max(x['lat'] for x in markers)-min(x['lat'] for x in markers):.3f}°")
            c3.metric("Lon span", f"{max(x['lon'] for x in markers)-min(x['lon'] for x in markers):.3f}°")

# ════════════════════════════════════════════════════════════════════════════════
# 🌍  CHOROPLETH
# ════════════════════════════════════════════════════════════════════════════════
elif mode == "🌍 Choropleth Map":
    st.subheader("🌍 Choropleth Map")
    st.caption("Upload a CSV (country, value) or use the built-in sample data.")

    col1, col2 = st.columns([1, 2.5])
    with col1:
        f = st.file_uploader("CSV (country, value)", type="csv")
        df = pd.read_csv(f) if f else pd.DataFrame({
            "country":["Malaysia","Indonesia","Thailand","Singapore","Philippines",
                       "Vietnam","Myanmar","Cambodia","China","Japan",
                       "South Korea","India","Australia","United States","Brazil"],
            "value":  [88,76,71,95,64,59,42,38,82,93,87,70,91,96,68],
        })
        vcol   = st.selectbox("Value column", [c for c in df.columns if c!="country"])
        scheme = st.selectbox("Colour scheme", ["YlOrRd","Blues","Greens","PuRd","Oranges"])
        opa    = st.slider("Opacity", 0.1, 1.0, 0.7)
        st.dataframe(df[["country",vcol]].head(10), height=200, use_container_width=True)

    with col2:
        geo = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
        m = folium.Map(location=[20,0], zoom_start=2, tiles=tile_layer)
        ch = folium.Choropleth(geo_data=geo, data=df, columns=["country",vcol],
            key_on="feature.properties.name", fill_color=scheme,
            fill_opacity=opa, line_opacity=0.3, legend_name=vcol,
            nan_fill_color="#cccccc", highlight=True).add_to(m)
        ch.geojson.add_child(folium.features.GeoJsonTooltip(["name"], labels=False))
        st_folium(m, width="100%", height=540)
        c1,c2,c3 = st.columns(3)
        c1.metric("Countries", len(df))
        c2.metric("Max", df[vcol].max())
        c3.metric("Average", f"{df[vcol].mean():.1f}")

# ════════════════════════════════════════════════════════════════════════════════
# 🛣️  ROUTE PLANNER
# ════════════════════════════════════════════════════════════════════════════════
elif mode == "🛣️ Route Planner":
    st.subheader("🛣️ Route Planner")
    st.caption("Enter 2–8 waypoints. Routes are calculated by OSRM.")

    col1, col2 = st.columns([1, 2.2])
    with col1:
        n = st.number_input("Number of stops", 2, 8, 3)
        default_coords = [
            (3.1390, 101.6869),
            (2.9264, 101.6964),
            (2.9213, 101.6559),
            (3.0738, 101.5183),
            (3.0449, 101.4428),
        ]
        stop_coords = []
        for i in range(int(n)):
            icon = "🏁" if i==0 else ("🏆" if i==int(n)-1 else "📍")
            st.markdown(f"**{icon} Stop {i+1}**")
            dlat, dlon = default_coords[i] if i < len(default_coords) else (3.1390, 101.6869)
            c1s, c2s = st.columns(2)
            slt = c1s.number_input("Lat", value=dlat, format="%.6f", key=f"slat{i}")
            sln = c2s.number_input("Lon", value=dlon, format="%.6f", key=f"slon{i}")
            stop_coords.append((slt, sln))
        rcol  = st.color_picker("Route colour", "#e06820")
        swpts = st.checkbox("Show waypoint markers", True)

    with col2:
        coords, resolved = [], []
        for i, (slt, sln) in enumerate(stop_coords):
            coords.append((slt, sln))
            resolved.append({"name": f"Stop {i+1}", "lat": slt, "lon": sln})

        center = coords[0] if coords else (3.139,101.687)
        m = folium.Map(location=list(center), zoom_start=zoom, tiles=tile_layer)
        dk, dm = None, None
        if len(coords)>=2:
            rt, dk, dm = osrm_route(coords)
            if rt:
                folium.PolyLine(rt, weight=5, color=rcol, opacity=0.9,
                    tooltip=f"{dk} km · {dm} min").add_to(m)
                from folium.plugins import AntPath
                AntPath(rt, weight=3, color="#fff", opacity=0.4, delay=800).add_to(m)
            else:
                st.warning("OSRM could not compute a route.")
        if swpts:
            for i,pt in enumerate(resolved):
                ic = "green" if i==0 else ("red" if i==len(resolved)-1 else "blue")
                folium.Marker([pt["lat"],pt["lon"]], tooltip=f"Stop {i+1}: {pt['name']}",
                    icon=folium.Icon(color=ic, icon="map-marker", prefix="fa")).add_to(m)
        st_folium(m, width="100%", height=500)
        c1,c2,c3 = st.columns(3)
        c1.metric("Waypoints", len(resolved))
        c2.metric("Distance", f"{dk or '—'} km")
        c3.metric("Drive time", f"{dm or '—'} min")

# ════════════════════════════════════════════════════════════════════════════════
# 🔍  POI EXPLORER
# ════════════════════════════════════════════════════════════════════════════════
else:
    st.subheader("🔍 POI Explorer")
    st.caption("Find nearby amenities using the Overpass API (OSM).")

    AMENITIES = {
        "🍽️ Restaurant":"restaurant","☕ Cafe":"cafe","🏥 Hospital":"hospital",
        "🏦 Bank / ATM":"bank","⛽ Fuel Station":"fuel","🏫 School":"school",
        "🏛️ Place of Worship":"place_of_worship","🅿️ Parking":"parking",
        "🏪 Supermarket":"supermarket","💊 Pharmacy":"pharmacy",
    }
    col1, col2 = st.columns([1, 2.2])
    with col1:
        st.markdown("**📍 Centre Coordinates**")
        lat  = st.number_input("Latitude", value=3.1570, format="%.6f", key="poi_lat")
        lon  = st.number_input("Longitude", value=101.7123, format="%.6f", key="poi_lon")
        rad   = st.slider("Radius (m)", 200, 5000, 1000, 100)
        amlbl = st.selectbox("Amenity type", list(AMENITIES.keys()))
        pcol  = st.color_picker("POI colour", "#3fb950")

    with col2:

        m = folium.Map(location=[lat,lon], zoom_start=zoom, tiles=tile_layer)
        folium.Circle([lat,lon], radius=rad, color="#58a6ff",
            fill=True, fill_opacity=0.07, weight=1.5).add_to(m)
        folium.Marker([lat,lon], tooltip="Search centre",
            icon=folium.Icon(color="blue", icon="crosshairs", prefix="fa")).add_to(m)

        with st.spinner(f"Searching for {amlbl}…"):
            pois = overpass_pois(lat, lon, rad, AMENITIES[amlbl])

        from folium.plugins import MarkerCluster
        mc = MarkerCluster().add_to(m)
        for p in pois:
            nm = p.get("tags",{}).get("name", amlbl)
            folium.CircleMarker([p["lat"],p["lon"]], radius=7,
                color=pcol, fill=True, fill_color=pcol, fill_opacity=0.9,
                tooltip=nm,
                popup=folium.Popup(f"<b>{nm}</b><br>{p['lat']:.5f}, {p['lon']:.5f}", max_width=200),
            ).add_to(mc)
        st_folium(m, width="100%", height=500)

        c1,c2,c3 = st.columns(3)
        c1.metric("POIs found", len(pois))
        c2.metric("Radius", f"{rad}m")
        c3.metric("Type", AMENITIES[amlbl])

        if pois:
            df_p = pd.DataFrame([{"Nama":p.get("tags",{}).get("name","—"),
                "Lat":p["lat"],"Lon":p["lon"],"OSM ID":p["id"]} for p in pois])
            with st.expander("📋 POI data table"):
                st.dataframe(df_p, use_container_width=True)
            st.download_button("⬇️ Download CSV", df_p.to_csv(index=False), "poi.csv", "text/csv")
