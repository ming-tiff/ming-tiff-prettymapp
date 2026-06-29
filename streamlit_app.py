import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import polyline
import random

st.set_page_config(page_title="Peta Cantik", page_icon="🗺️", layout="wide")

st.title('🗺️ Peta Cantik')
st.write('Peta interaktif bergaya retro — powered by OpenStreetMap.')

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
    st.header("⚙️ Tetapan")
    mode = st.selectbox("Mod Peta", [
        "🎨 Peta Retro Bandar",
        "📍 Peta Penanda",
        "🌍 Peta Koropleth",
        "🛣️ Perancang Laluan",
        "🔍 Penjelajah POI",
    ])
    zoom = st.slider("Zum Lalai", 2, 18, 14)
    tile = st.selectbox("Lapisan Peta", {
        "CartoDB Positron":  "CartoDB positron",
        "CartoDB Gelap":     "CartoDB dark_matter",
        "OpenStreetMap":     "OpenStreetMap",
    }.keys())
    TILES = {
        "CartoDB Positron":  "CartoDB positron",
        "CartoDB Gelap":     "CartoDB dark_matter",
        "OpenStreetMap":     "OpenStreetMap",
    }
    tile_layer = TILES[tile]
    st.info("Data: OpenStreetMap · Routing: OSRM · Geocoding: Nominatim")

st.divider()

# ════════════════════════════════════════════════════════════════════════════════
# 🎨  RETRO BANDAR
# ════════════════════════════════════════════════════════════════════════════════
if mode == "🎨 Peta Retro Bandar":
    st.subheader("🎨 Peta Retro Bandar")
    st.caption("Bangunan OSM dicat dengan palet warna hangat — krim, oren, merah.")

    col1, col2 = st.columns([1, 2.5])
    with col1:
        city  = st.text_input("Lokasi", "Kuala Lumpur City Centre, Malaysia")
        rad   = st.slider("Jejari (m)", 100, 1200, 400, 50)
        tips  = st.checkbox("Tunjuk tooltip bangunan", True)
        st.markdown("**Palet warna**")
        legend = [("#f5e6a3","Industri"),("#f0c070","Kediaman"),
                  ("#f0a040","Pangsapuri"),("#e06820","Komersial"),
                  ("#c83010","Runcit / Hotel"),("#a01808","Hospital / Gereja")]
        for hx, lb in legend:
            st.markdown(
                f'<span style="background:{hx};padding:2px 10px;border-radius:3px;'
                f'border:1px solid #888;margin-right:6px;font-size:.8rem">&nbsp;</span>{lb}',
                unsafe_allow_html=True)

    with col2:
        lat, lon, disp = geocode(city)
        if not lat:
            st.error("Lokasi tidak dijumpai.")
            st.stop()

        with st.spinner("Mengambil bangunan dari Overpass…"):
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
        st.markdown(f"**{count}** bangunan dipaparkan · jejari **{rad}m** · {city.split(',')[0].upper()}")

# ════════════════════════════════════════════════════════════════════════════════
# 📍  MARKER MAP
# ════════════════════════════════════════════════════════════════════════════════
elif mode == "📍 Peta Penanda":
    st.subheader("📍 Peta Penanda")
    st.caption("Masukkan koordinat, nama tempat, atau muat naik CSV.")

    col1, col2 = st.columns([1, 2])
    with col1:
        method = st.radio("Kaedah Input", ["Koordinat Manual","Nama Tempat","Muat Naik CSV"])
        markers = []

        if method == "Koordinat Manual":
            n = st.number_input("Bilangan titik", 1, 10, 3)
            for i in range(int(n)):
                a, b, c = st.columns([2,2,3])
                lt = a.number_input(f"Lat {i+1}", value=3.139+i*0.02, format="%.4f", key=f"la{i}")
                ln = b.number_input(f"Lon {i+1}", value=101.687+i*0.02, format="%.4f", key=f"lo{i}")
                lb = c.text_input(f"Label {i+1}", value=f"Titik {i+1}", key=f"lb{i}")
                markers.append({"lat":lt,"lon":ln,"label":lb})

        elif method == "Nama Tempat":
            raw = st.text_area("Nama tempat (satu baris satu)", "Kuala Lumpur\nPetronas Twin Towers\nBatu Caves", height=110)
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

        color   = st.color_picker("Warna penanda", "#e06820")
        cluster = st.checkbox("Pengelompokan", True)

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
            c1.metric("Penanda", len(markers))
            c2.metric("Lat span", f"{max(x['lat'] for x in markers)-min(x['lat'] for x in markers):.3f}°")
            c3.metric("Lon span", f"{max(x['lon'] for x in markers)-min(x['lon'] for x in markers):.3f}°")

# ════════════════════════════════════════════════════════════════════════════════
# 🌍  CHOROPLETH
# ════════════════════════════════════════════════════════════════════════════════
elif mode == "🌍 Peta Koropleth":
    st.subheader("🌍 Peta Koropleth")
    st.caption("Muat naik CSV (country, value) atau guna data contoh.")

    col1, col2 = st.columns([1, 2.5])
    with col1:
        f = st.file_uploader("CSV (country, value)", type="csv")
        df = pd.read_csv(f) if f else pd.DataFrame({
            "country":["Malaysia","Indonesia","Thailand","Singapore","Philippines",
                       "Vietnam","Myanmar","Cambodia","China","Japan",
                       "South Korea","India","Australia","United States","Brazil"],
            "value":  [88,76,71,95,64,59,42,38,82,93,87,70,91,96,68],
        })
        vcol   = st.selectbox("Lajur nilai", [c for c in df.columns if c!="country"])
        scheme = st.selectbox("Skema warna", ["YlOrRd","Blues","Greens","PuRd","Oranges"])
        opa    = st.slider("Kelegapan", 0.1, 1.0, 0.7)
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
        c1.metric("Negara", len(df))
        c2.metric("Maks", df[vcol].max())
        c3.metric("Purata", f"{df[vcol].mean():.1f}")

# ════════════════════════════════════════════════════════════════════════════════
# 🛣️  ROUTE PLANNER
# ════════════════════════════════════════════════════════════════════════════════
elif mode == "🛣️ Perancang Laluan":
    st.subheader("🛣️ Perancang Laluan")
    st.caption("Masukkan 2–8 titik henti. Laluan dikira oleh OSRM.")

    col1, col2 = st.columns([1, 2.2])
    with col1:
        n = st.number_input("Bilangan henti", 2, 8, 3)
        defaults = ["Kuala Lumpur","Putrajaya","Cyberjaya","Shah Alam","Klang"]
        stops = [st.text_input(
            ("🏁" if i==0 else "🏆" if i==int(n)-1 else "📍")+f" Henti {i+1}",
            value=defaults[i] if i<len(defaults) else "", key=f"s{i}")
            for i in range(int(n))]
        rcol  = st.color_picker("Warna laluan", "#e06820")
        swpts = st.checkbox("Tunjuk penanda henti", True)

    with col2:
        coords, resolved = [], []
        for s in stops:
            s = s.strip()
            if not s: continue
            parts = s.split(",")
            if len(parts)==2:
                try:
                    lt,ln=float(parts[0]),float(parts[1])
                    coords.append((lt,ln)); resolved.append({"name":s,"lat":lt,"lon":ln}); continue
                except ValueError: pass
            lt,ln,_ = geocode(s)
            if lt: coords.append((lt,ln)); resolved.append({"name":s,"lat":lt,"lon":ln})

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
                st.warning("OSRM tidak dapat mengira laluan.")
        if swpts:
            for i,pt in enumerate(resolved):
                ic = "green" if i==0 else ("red" if i==len(resolved)-1 else "blue")
                folium.Marker([pt["lat"],pt["lon"]], tooltip=f"Henti {i+1}: {pt['name']}",
                    icon=folium.Icon(color=ic, icon="map-marker", prefix="fa")).add_to(m)
        st_folium(m, width="100%", height=500)
        c1,c2,c3 = st.columns(3)
        c1.metric("Titik henti", len(resolved))
        c2.metric("Jarak", f"{dk or '—'} km")
        c3.metric("Masa pandu", f"{dm or '—'} min")

# ════════════════════════════════════════════════════════════════════════════════
# 🔍  POI EXPLORER
# ════════════════════════════════════════════════════════════════════════════════
else:
    st.subheader("🔍 Penjelajah POI")
    st.caption("Cari kemudahan berdekatan menggunakan Overpass API (OSM).")

    AMENITIES = {
        "🍽️ Restoran":"restaurant","☕ Kafe":"cafe","🏥 Hospital":"hospital",
        "🏦 Bank / ATM":"bank","⛽ Stesen Minyak":"fuel","🏫 Sekolah":"school",
        "🏛️ Rumah Ibadat":"place_of_worship","🅿️ Tempat Letak Kereta":"parking",
        "🏪 Pasar Raya":"supermarket","💊 Farmasi":"pharmacy",
    }
    col1, col2 = st.columns([1, 2.2])
    with col1:
        loc   = st.text_input("Lokasi pusat", "Kuala Lumpur City Centre")
        rad   = st.slider("Jejari (m)", 200, 5000, 1000, 100)
        amlbl = st.selectbox("Jenis kemudahan", list(AMENITIES.keys()))
        pcol  = st.color_picker("Warna POI", "#3fb950")

    with col2:
        lat, lon, _ = geocode(loc)
        if not lat: lat, lon = 3.157, 101.712

        m = folium.Map(location=[lat,lon], zoom_start=zoom, tiles=tile_layer)
        folium.Circle([lat,lon], radius=rad, color="#58a6ff",
            fill=True, fill_opacity=0.07, weight=1.5).add_to(m)
        folium.Marker([lat,lon], tooltip="Pusat carian",
            icon=folium.Icon(color="blue", icon="crosshairs", prefix="fa")).add_to(m)

        with st.spinner(f"Mencari {amlbl}…"):
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
        c1.metric("POI dijumpai", len(pois))
        c2.metric("Jejari", f"{rad}m")
        c3.metric("Jenis", AMENITIES[amlbl])

        if pois:
            df_p = pd.DataFrame([{"Nama":p.get("tags",{}).get("name","—"),
                "Lat":p["lat"],"Lon":p["lon"],"OSM ID":p["id"]} for p in pois])
            with st.expander("📋 Jadual data POI"):
                st.dataframe(df_p, use_container_width=True)
            st.download_button("⬇️ Muat turun CSV", df_p.to_csv(index=False), "poi.csv", "text/csv")
