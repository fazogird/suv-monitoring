import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import shapely
import warnings
import numpy as np

# --- 1. SOZLAMALAR / SETTINGS ---
warnings.filterwarnings('ignore') 
pd.options.mode.chained_assignment = None 
st.set_page_config(layout="wide", page_title="Suv Monitoringi | Water Monitoring")

# --- CSS: IXCHAMLASHTIRISH, DARK MODENI O'CHIRISH VA TOOLTIPNI TUZATISH ---
st.markdown("""
<style>
    /* 1. MAJBURIY OQ FON (Force Light Mode) */
    :root {
        --primary-color: #0068C9;
        --background-color: #FFFFFF;
        --secondary-background-color: #F0F2F6;
        --text-color: #262730;
        --font: "sans serif";
    }
    [data-testid="stAppViewContainer"] {
        background-color: var(--background-color);
        color: var(--text-color);
    }
    [data-testid="stSidebar"] {
        background-color: var(--secondary-background-color);
        color: var(--text-color);
    }
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0);
    }
    
    /* 2. ORTIQCHA TUGMALARNI YASHIRISH */
    .stDeployButton, #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"], .viewerBadge_container__1QSob {display: none;}

    /* 3. LAYOUT */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    div[data-testid="stMetric"] {
        background-color: #F8F9FB;
        border: 1px solid #D6D9E0;
        padding: 10px;
        border-radius: 8px;
    }
    h1 {
        font-size: 1.6rem !important;
        margin-bottom: 1rem !important;
    }

    /* 4. TOOLTIP RANGINI TUZATISH (Majburan OQ) */
    .deckgl-tooltip > div {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. MA'LUMOTNI YUKLASH / LOAD DATA ---
@st.cache_data
def load_data():
    FILE_PATH = "Test-area.shp"   
    
    gdf = gpd.read_file(FILE_PATH)
    
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    gdf.geometry = shapely.force_2d(gdf.geometry)
    
    gdf['SIJ_m3ga'] = pd.to_numeric(gdf['SIJ_m3ga'], errors='coerce').fillna(0)
    
    months = ['03','04','05','06','07','08','09','10']
    for m in months:
        if f'SI_{m}_m3' not in gdf.columns: gdf[f'SI_{m}_m3'] = 0
        if f'SS_{m}_m3' not in gdf.columns: gdf[f'SS_{m}_m3'] = 0
        
        gdf[f'SI_{m}_m3'] = pd.to_numeric(gdf[f'SI_{m}_m3'], errors='coerce').fillna(0)
        gdf[f'SS_{m}_m3'] = pd.to_numeric(gdf[f'SS_{m}_m3'], errors='coerce').fillna(0)

    if 'crop_en' in gdf.columns:
        gdf['crop_en'] = gdf['crop_en'].fillna("Boshqa | Other")
    else:
        gdf['crop_en'] = "Noma'lum | Unknown"
        
    if 'area_ha' not in gdf.columns:
        gdf_metric = gdf.to_crs(epsg=32642) 
        gdf['area_ha'] = gdf_metric.geometry.area / 10000
    
    gdf['area_ha'] = pd.to_numeric(gdf['area_ha'], errors='coerce').fillna(0)
    
    return gdf

try:
    df_master = load_data()
except Exception as e:
    st.error(f"Ma'lumot o'qishda xatolik | Data Load Error: {e}")
    st.stop()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Sozlamalar | Settings")
    
    crops = df_master['crop_en'].unique()
    sel_crop = st.multiselect("Ekin turi (Crop Type):", options=crops, default=crops[:1] if len(crops)>0 else None)
    
    month_map = {
        'Mart | Mar':'03', 'Aprel | Apr':'04', 'May | May':'05', 'Iyun | Jun':'06', 
        'Iyul | Jul':'07', 'Avgust | Aug':'08', 'Sentabr | Sep':'09', 'Oktabr | Oct':'10'
    }
    sel_months_names = st.multiselect("Oylarni tanlang (Select Months):", options=list(month_map.keys()), default=list(month_map.keys()))

# --- 4. HISOBLASH ---
if not sel_crop: 
    df = df_master.copy()
else: 
    df = df_master[df_master['crop_en'].isin(sel_crop)].copy()

if not sel_months_names:
    df['Current_Demand'] = 0
    df['Current_Supply'] = 0
else:
    target_suffixes = [month_map[m] for m in sel_months_names]
    df['Current_Demand'] = df[[f'SI_{c}_m3' for c in target_suffixes]].sum(axis=1)
    df['Current_Supply'] = df[[f'SS_{c}_m3' for c in target_suffixes]].sum(axis=1)

# Asosiy hisob-kitob
df['Current_Demand_Ha'] = np.where(df['area_ha'] > 0, df['Current_Demand'] / df['area_ha'], 0)

# --- MUHIM: YAXLITLASH (TOOLTIP UCHUN) ---
df['display_demand_ha'] = df['Current_Demand_Ha'].round(2)
df['display_demand_total'] = df['Current_Demand'].round(2)
df['display_area'] = df['area_ha'].round(2)

# --- 5. KPI PANEL ---
st.title("🛰️ Ekin Yerlari Suv Monitoringi | Field Water Monitoring (ET)")

total_area = df['area_ha'].sum()
total_dem = df['Current_Demand'].sum() / 1_000_000 
total_sup = df['Current_Supply'].sum() / 1_000_000 

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tanlangan Dalalar | Selected Fields", f"{len(df):,}")
c2.metric("Jami Maydon | Total Area", f"{total_area:,.0f} ga")
c3.metric("Suv Istemoli (ET) | Demand", f"{total_dem:,.2f} mln m³")
c4.metric("Suv Sarfi (Irrigation) | Supply", f"{total_sup:,.2f} mln m³", delta=f"{total_sup - total_dem:.2f}")

st.markdown("---")

# --- 6. ASOSIY EKRAN ---
col_map, col_stats = st.columns([2.5, 1]) 

with col_map:
    # --- XARITA ---
    def get_neon_colors(val):
        if val < 2000: return [0, 255, 255, 180]    # CYAN
        elif val < 5000: return [0, 255, 0, 180]    # LIME
        elif val < 9000: return [255, 255, 0, 180]  # YELLOW
        elif val < 14000: return [255, 165, 0, 180] # ORANGE
        else: return [255, 0, 0, 180]               # RED

    df['fill_color'] = df['Current_Demand_Ha'].map(get_neon_colors)

    # --- MUHIM: TOOLTIP (Yaxlitlangan ustunlarni chaqiramiz) ---
    tooltip = {
        "html": "<div style='font-family:sans-serif; color:white; background:#111; padding:10px; border:1px solid cyan; border-radius:5px;'>"
                "<b>ID:</b> {id} <br/>"
                "<b>Maydon | Area:</b> {display_area} ga <br/>"
                "<b>Suv Iste'moli(ET):</b> {display_demand_ha} m³/ga <br/>"
                "<b>Suv Iste'moli(ET):</b> {display_demand_total} m³"
                "</div>",
        "style": {"color": "white"}
    }

    view_state = pdk.ViewState(
        latitude=df.geometry.centroid.y.mean(),
        longitude=df.geometry.centroid.x.mean(),
        zoom=10.5, pitch=0
    )

    layer = pdk.Layer(
        "GeoJsonLayer", df,
        get_fill_color="fill_color",
        get_line_color=[255, 255, 255], get_line_width=5,
        filled=True, stroked=True, pickable=True, auto_highlight=True, opacity=1
    )

    st.pydeck_chart(pdk.Deck(
        layers=[layer], initial_view_state=view_state, 
        map_style=pdk.map_styles.CARTO_DARK,
        tooltip=tooltip
    ), use_container_width=True, height=600) 

with col_stats:
    # --- ANALITIKA ---
    
    # 1. GRAFIK
    st.markdown("##### 📈 Oylik Dinamika | Monthly Dynamics")
    months_code = ['03','04','05','06','07','08','09','10']
    names = ['Mar','Apr','May','Jun','Jul','Aug','Sep','Oct']
    
    y_sup = [df[f'SS_{m}_m3'].sum() for m in months_code]
    y_dem = [df[f'SI_{m}_m3'].sum() for m in months_code]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=names, y=y_sup, name="Sarf (Supply)", line=dict(color='#0068C9', width=2)))
    fig.add_trace(go.Scatter(x=names, y=y_dem, name="Talab (Demand)", line=dict(color='#FF2B2B', width=2, dash='dot')))
    
    fig.update_layout(
        height=250,
        margin=dict(t=10,b=0,l=0,r=0),
        legend=dict(orientation="h", y=1.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 2. JADVAL
    st.markdown("##### 🚨 Top 'Chanqoq' Dalalar | Top 'Thirsty' Fields")
    
    # ID ustunini aniqlash (xatolik bermasligi uchun)
    id_col = 'id' if 'id' in df.columns else df.index.name if df.index.name else 'index'
    
    # Tartiblash va kerakli ustunlarni olish
    top = df[[id_col, 'area_ha', 'Current_Demand_Ha']].sort_values('Current_Demand_Ha', ascending=False).head(8)
    
    st.dataframe(
        top.style.format("{:.0f}").background_gradient(cmap="Reds", subset=['Current_Demand_Ha']),
        use_container_width=True,
        height=300 
    )

