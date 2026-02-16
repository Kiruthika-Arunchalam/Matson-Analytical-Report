# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(layout="wide", page_title="Matson Schedule Dashboard")

# =====================================================
# DARK THEME FUNCTION (GLOBAL)
# =====================================================
def apply_dark(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="white"),
        legend=dict(font=dict(color="white"))
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.15)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.15)")
    return fig

# =====================================================
# CSS
# =====================================================
st.markdown("""
<style>
.stApp { background-color: #0b0b0b; color: #ffffff; }
section[data-testid="stSidebar"] { background-color: #0b0b0b; }
h1, h2 { color: #0096c7 !important; font-weight: 800 !important; }
h3 { color: #ffdab9 !important; font-weight: 700 !important; }
div[data-testid="metric-container"] {
    background-color: #000000;
    border-radius: 8px;
    padding: 12px;
}
div[data-testid="metric-container"] label {
    color: #0096c7 !important;
}
div[data-testid="metric-container"] div {
    color: #0096c7 !important;
    font-weight: 800 !important;
    font-size: 26px !important;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# LOAD DATA (BACKEND ONLY)
# =====================================================
DATA_FILE = "shipping_schedule_enriched.csv"  # place file in same folder

try:
    df = pd.read_csv(DATA_FILE)
except Exception as e:
    st.error(f"Error loading file: {e}")
    st.stop()

if df.empty:
    st.error("Data file is empty.")
    st.stop()

df.columns = df.columns.str.strip()

# =====================================================
# DATE PARSING (SAFE)
# =====================================================
df["arrive_dt"] = pd.to_datetime(df.get("arrive_dt"), errors="coerce")
df["final_depart"] = pd.to_datetime(
    df.get("final_imputed_depart_dt", df.get("depart_dt")),
    errors="coerce"
)

# =====================================================
# DERIVED FIELDS
# =====================================================
df["Vessel_Name"] = df.get("Vessel_Name", "")
df["Voyage"] = df.get("Voyage", "")
df["Bound"] = df.get("Bound", "")

df["vessvoy"] = (
    df["Vessel_Name"].astype(str) + "*" +
    df["Voyage"].astype(str) + "*" +
    df["Bound"].astype(str)
)

df = df.sort_values(["vessvoy", "final_depart"])
df["port_call_index"] = df.groupby("vessvoy").cumcount() + 1

df["transit_hours"] = (
    df["arrive_dt"] - df["final_depart"]
).dt.total_seconds() / 3600

df["route"] = (
    df.get("OriginPortCode","").astype(str) + "-" +
    df.get("DestPortCode","").astype(str)
)

# =====================================================
# SIDEBAR FILTERS
# =====================================================
st.sidebar.header("Filters")

date_min = df["arrive_dt"].min()
date_max = df["arrive_dt"].max()

if pd.notna(date_min) and pd.notna(date_max):
    date_range = st.sidebar.date_input(
        "Arrival Date Range",
        [date_min.date(), date_max.date()]
    )
else:
    date_range = None

vessel_filter = st.sidebar.multiselect(
    "Vessel",
    sorted(df["Vessel_Name"].dropna().unique())
)

origin_filter = st.sidebar.multiselect(
    "Origin Port",
    sorted(df["OriginPortCode"].dropna().unique())
)

dest_filter = st.sidebar.multiselect(
    "Destination Port",
    sorted(df["DestPortCode"].dropna().unique())
)

# APPLY FILTERS
df_f = df.copy()

if date_range:
    df_f = df_f[
        (df_f["arrive_dt"] >= pd.to_datetime(date_range[0])) &
        (df_f["arrive_dt"] <= pd.to_datetime(date_range[1]) + pd.Timedelta(days=1))
    ]

if vessel_filter:
    df_f = df_f[df_f["Vessel_Name"].isin(vessel_filter)]

if origin_filter:
    df_f = df_f[df_f["OriginPortCode"].isin(origin_filter)]

if dest_filter:
    df_f = df_f[df_f["DestPortCode"].isin(dest_filter)]

# =====================================================
# TITLE
# =====================================================
st.title("Matson Schedule Data Analysis Report")

# =====================================================
# KPIs
# =====================================================
st.header("Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Rows", len(df_f))
c2.metric("Voyages", df_f["vessvoy"].nunique())
c3.metric("Vessels", df_f["Vessel_Name"].nunique())

avg_transit = df_f["transit_hours"].mean()
c4.metric("Avg Transit (hrs)", f"{avg_transit:.1f}" if not np.isnan(avg_transit) else "N/A")

# =====================================================
# DEPART DISTRIBUTION
# =====================================================
st.subheader("Departure Count by Date")

if df_f["final_depart"].notna().any():

    dep = (
        df_f["final_depart"]
        .dropna()
        .dt.floor("D")
        .value_counts()
        .rename_axis("date")
        .reset_index(name="count")
        .sort_values("date")
    )

    fig = px.line(dep, x="date", y="count", markers=True)
    st.plotly_chart(apply_dark(fig), use_container_width=True)

    # Interpretation
    mean_c = dep["count"].mean()
    std_c = dep["count"].std()

    if dep["count"].max() > mean_c + 3 * std_c:
        st.warning("⚠️ Abnormal departure spike detected.")
    else:
        st.success("✅ Departure pattern appears stable.")

# =====================================================
# TOP PORTS
# =====================================================
st.subheader("Top Origin & Destination Ports")

col1, col2 = st.columns(2)

with col1:
    if df_f["OriginPortCode"].notna().any():
        top_o = df_f["OriginPortCode"].value_counts().head(15).reset_index()
        top_o.columns = ["Origin", "count"]
        fig_o = px.bar(top_o, x="count", y="Origin", orientation="h")
        st.plotly_chart(apply_dark(fig_o), use_container_width=True)

with col2:
    if df_f["DestPortCode"].notna().any():
        top_d = df_f["DestPortCode"].value_counts().head(15).reset_index()
        top_d.columns = ["Destination", "count"]
        fig_d = px.bar(top_d, x="count", y="Destination", orientation="h")
        st.plotly_chart(apply_dark(fig_d), use_container_width=True)

# =====================================================
# TRANSIT VS PORT CALL
# =====================================================
st.subheader("Transit Hours vs Port Call Index")

sc = df_f.dropna(subset=["transit_hours", "port_call_index"])

if not sc.empty:

    fig_sc = px.scatter(
        sc,
        x="port_call_index",
        y="transit_hours",
        color="route",
        hover_data=["OriginPortCode","DestPortCode","vessvoy"]
    )

    st.plotly_chart(apply_dark(fig_sc), use_container_width=True)

    corr = sc[["port_call_index","transit_hours"]].corr().iloc[0,1]

    if corr > 0.6:
        st.warning("⚠️ Delay accumulation detected across port calls.")
    else:
        st.success("✅ Transit behavior stable.")

# =====================================================
# GANTT TIMELINE
# =====================================================
st.subheader("Voyage Timeline (Gantt)")

voy_list = sorted(df_f["vessvoy"].dropna().unique())
sel_voy = st.multiselect("Select Voyages (max 10)", voy_list, default=voy_list[:5])

if sel_voy:

    gantt_df = df_f[
        df_f["vessvoy"].isin(sel_voy) &
        df_f["arrive_dt"].notna() &
        df_f["final_depart"].notna()
    ]

    if not gantt_df.empty:

        fig_g = px.timeline(
            gantt_df,
            x_start="final_depart",
            x_end="arrive_dt",
            y="vessvoy",
            color="route",
            hover_data=["OriginPortCode","DestPortCode"]
        )

        fig_g.update_yaxes(autorange="reversed")
        st.plotly_chart(apply_dark(fig_g), use_container_width=True)

        durations = (gantt_df["arrive_dt"] - gantt_df["final_depart"]).dt.total_seconds() / 3600

        if (durations > durations.quantile(0.95)).mean() > 0.15:
            st.warning("⚠️ Some voyages have unusually long durations.")
        else:
            st.success("✅ Voyage schedule looks consistent.")

# =====================================================
# DATA PREVIEW
# =====================================================
st.subheader("Data Preview")
st.dataframe(df_f.head(200))

st.success("Dashboard loaded successfully 🚢")
