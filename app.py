# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(
    layout="wide",
    page_title="Matson Schedule Data Analysis"
)

# ===============================
# GLOBAL DARK CSS
# ===============================
st.markdown("""
<style>
.stApp { background-color: #0b0b0b; color: #ffffff; }

section[data-testid="stSidebar"] {
    background-color: #0b0b0b;
}

section[data-testid="stSidebar"] label {
    color: #8ecae6 !important;
    font-weight: 600;
}

div[data-testid="metric-container"] {
    background-color: #000000;
    border-radius: 8px;
    padding: 14px;
}

div[data-testid="metric-container"] label {
    color: #8ecae6 !important;
    font-weight: 700;
}

div[data-testid="metric-container"] div {
    color: #00b4d8 !important;
    font-weight: 800 !important;
    font-size: 26px !important;
}

h1 { color: #669bbc!important; }
h2, h3 { color: #d4a373 !important; }

</style>
""", unsafe_allow_html=True)

# ===============================
# DARK THEME FUNCTION
# ===============================
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


# ===============================
# LOAD DATA
# ===============================
DATA_FILE = os.path.join("data", "shipping_schedule_enriched.csv")

if not os.path.exists(DATA_FILE):
    st.error("Data file not found in /data folder")
    st.stop()

df = pd.read_csv(DATA_FILE)
df.columns = df.columns.str.strip()

if df.empty:
    st.error("Data file is empty")
    st.stop()

# ===============================
# DATE PARSING (SAFE)
# ===============================
df["arrive_dt"] = pd.to_datetime(df.get("arrive_dt"), errors="coerce")

df["final_depart"] = pd.to_datetime(
    df.get("final_imputed_depart_dt", df.get("depart_dt")),
    errors="coerce"
)

# ===============================
# DERIVED FIELDS
# ===============================
df["vessvoy"] = (
    df.get("Vessel_Name", "").astype(str) + "*" +
    df.get("Voyage", "").astype(str) + "*" +
    df.get("Bound", "").astype(str)
)

df = df.sort_values(["vessvoy", "final_depart"])
df["port_call_index"] = df.groupby("vessvoy").cumcount() + 1

df["transit_hours"] = (
    df["arrive_dt"] - df["final_depart"]
).dt.total_seconds() / 3600

# ===============================
# SIDEBAR FILTERS
# ===============================
st.sidebar.header("Filters")

if df["arrive_dt"].notna().any():
    date_range = st.sidebar.date_input(
        "Arrival date range",
        [
            df["arrive_dt"].min().date(),
            df["arrive_dt"].max().date()
        ]
    )
else:
    date_range = None

vessels = st.sidebar.multiselect(
    "Vessel",
    sorted(df["Vessel_Name"].dropna().unique())
)

voyages = st.sidebar.multiselect(
    "Voyage",
    sorted(df["vessvoy"].dropna().unique())
)

origins = st.sidebar.multiselect(
    "Origin Port",
    sorted(df["OriginPortCode"].dropna().unique())
)

dests = st.sidebar.multiselect(
    "Destination Port",
    sorted(df["DestPortCode"].dropna().unique())
)

# ===============================
# APPLY FILTERS
# ===============================
df_f = df.copy()

if date_range:
    df_f = df_f[
        (df_f["arrive_dt"] >= pd.to_datetime(date_range[0])) &
        (df_f["arrive_dt"] <= pd.to_datetime(date_range[1]) + pd.Timedelta(days=1))
    ]

if vessels:
    df_f = df_f[df_f["Vessel_Name"].isin(vessels)]

if voyages:
    df_f = df_f[df_f["vessvoy"].isin(voyages)]

if origins:
    df_f = df_f[df_f["OriginPortCode"].isin(origins)]

if dests:
    df_f = df_f[df_f["DestPortCode"].isin(dests)]

# ===============================
# TITLE
# ===============================
st.title("Matson Schedule Data Analysis Report")
st.header("Overview")

# ===============================
# KPIs
# ===============================
c1, c2, c3, c4 = st.columns(4)

c1.metric("Rows", len(df_f))
c2.metric("Voyages", df_f["vessvoy"].nunique())
c3.metric("Vessels", df_f["Vessel_Name"].nunique())

avg_transit = df_f["transit_hours"].mean()
c4.metric("Avg Transit (hrs)", f"{avg_transit:.1f}" if not np.isnan(avg_transit) else "N/A")

# ===============================
# DEPARTURE DISTRIBUTION
# ===============================
st.subheader("Departure Count by Date")

dep = (
    df_f["final_depart"]
    .dropna()
    .dt.date
    .value_counts()
    .sort_index()
    .reset_index()
)

if not dep.empty:
    dep.columns = ["date", "count"]

    fig_dep = px.line(dep, x="date", y="count", markers=True)
    fig_dep.update_layout(xaxis_title="Date", yaxis_title="Count")
    st.plotly_chart(apply_dark(fig_dep), use_container_width=True)
    # ===============================
# INTERPRETATION: DEPARTURE DISTRIBUTION
# ===============================
if not dep.empty:

    mean_c = dep["count"].mean()
    std_c = dep["count"].std()
    peak = dep["count"].max()

    if peak > mean_c + 3 * std_c:
        st.warning(
            "⚠️ **Departure Clustering Detected**\n\n"
            "Certain dates show unusually high departures. "
            "This may indicate batch schedule uploads, duplicated entries, "
            "or peak-season deployment patterns."
        )
    elif std_c / mean_c > 0.75:
        st.info(
            "ℹ️ **High Operational Variability**\n\n"
            "Departure frequency varies significantly across dates. "
            "This may reflect seasonal routing or dynamic schedule adjustments."
        )
    else:
        st.success(
            "✅ **Stable Departure Pattern**\n\n"
            "Departures are evenly distributed across time, "
            "indicating consistent operational scheduling."
        )


# ===============================
# TOP PORTS
# ===============================
st.subheader("Top Origin & Destination Ports")

top_o = df_f["OriginPortCode"].value_counts().head(15).reset_index()
top_o.columns = ["OriginPortCode", "count"]

top_d = df_f["DestPortCode"].value_counts().head(15).reset_index()
top_d.columns = ["DestPortCode", "count"]

col1, col2 = st.columns(2)

with col1:
    fig_o = px.bar(
        top_o,
        x="count",
        y="OriginPortCode",
        orientation="h",
        hover_data=["OriginPortCode", "count"]
    )
    fig_o.update_traces(
        hovertemplate="<b>Origin:</b> %{y}<br><b>Movements:</b> %{x}<extra></extra>"
    )
    st.plotly_chart(apply_dark(fig_o), use_container_width=True)

with col2:
    fig_d = px.bar(
        top_d,
        x="count",
        y="DestPortCode",
        orientation="h",
        hover_data=["DestPortCode", "count"]
    )
    fig_d.update_traces(
        hovertemplate="<b>Destination:</b> %{y}<br><b>Movements:</b> %{x}<extra></extra>"
    )
    st.plotly_chart(apply_dark(fig_d), use_container_width=True)
    # ===============================
# INTERPRETATION: PORT CONCENTRATION
# ===============================
if not top_o.empty and not top_d.empty:

    total = len(df_f)
    top_origin_share = top_o["count"].iloc[0] / total
    top_dest_share = top_d["count"].iloc[0] / total

    if top_origin_share > 0.6 or top_dest_share > 0.6:
        st.warning(
            "⚠️ **High Port Dependency Risk**\n\n"
            "A single port dominates traffic. "
            "Operational disruptions at this port may significantly impact the network."
        )
    elif top_origin_share > 0.35 or top_dest_share > 0.35:
        st.info(
            "ℹ️ **Moderate Hub Concentration**\n\n"
            "Traffic is centered around key hub ports — typical in hub-and-spoke networks."
        )
    else:
        st.success(
            "✅ **Balanced Port Network**\n\n"
            "Traffic is well distributed across multiple ports, reducing concentration risk."
        )


# ===============================
# TRANSIT VS PORT CALL
# ===============================
st.subheader("Transit Hours vs Port Call Index")

sc = df_f.dropna(subset=["transit_hours", "port_call_index"])

if not sc.empty:

    fig_sc = px.scatter(
        sc,
        x="port_call_index",
        y="transit_hours",
        color="OriginPortCode",
        custom_data=["OriginPortCode", "DestPortCode", "Vessel_Name", "vessvoy"]
    )

    fig_sc.update_traces(
        hovertemplate=
        "<b>Origin:</b> %{customdata[0]}<br>" +
        "<b>Destination:</b> %{customdata[1]}<br>" +
        "<b>Vessel:</b> %{customdata[2]}<br>" +
        "<b>Voyage:</b> %{customdata[3]}<br>" +
        "<b>Transit Hours:</b> %{y:.1f}<br>" +
        "<b>Port Call Index:</b> %{x}<extra></extra>"
    )

    fig_sc.update_layout(
        xaxis_title="Port Call Index",
        yaxis_title="Transit Hours"
    )

    st.plotly_chart(apply_dark(fig_sc), use_container_width=True)
    # ===============================
# INTERPRETATION: TRANSIT BEHAVIOR
# ===============================
if not sc.empty:

    corr = sc[["port_call_index", "transit_hours"]].corr().iloc[0, 1]
    outlier_ratio = (
        sc["transit_hours"] >
        sc["transit_hours"].quantile(0.95)
    ).mean()

    if corr > 0.6:
        st.warning(
            "⚠️ **Cascading Delay Pattern**\n\n"
            "Transit times increase as voyages progress. "
            "This suggests delay accumulation across port calls."
        )
    elif corr < -0.5:
        st.info(
            "ℹ️ **Efficiency Gain Across Voyage**\n\n"
            "Transit time reduces across later port calls, "
            "indicating route optimization or shorter legs."
        )
    elif outlier_ratio > 0.1:
        st.warning(
            "⚠️ **Significant Transit Outliers Detected**\n\n"
            "A notable percentage of voyages show unusually high transit hours."
        )
    else:
        st.success(
            "✅ **Stable Transit Performance**\n\n"
            "Transit duration remains consistent across port sequences."
        )


# ===============================
# GANTT TIMELINE
# ===============================
st.subheader("Voyage Timeline (Gantt)")

vv_list = sorted(df_f["vessvoy"].dropna().unique())

if vv_list:

    vv_select = st.multiselect(
        "Select voyages (max 10)",
        vv_list,
        default=vv_list[:5]
    )

    gantt_df = df_f[
        df_f["vessvoy"].isin(vv_select) &
        df_f["OriginPortCode"].notna() &
        df_f["final_depart"].notna() &
        df_f["arrive_dt"].notna()
    ]

    if not gantt_df.empty:

        fig_g = px.timeline(
            gantt_df,
            x_start="final_depart",
            x_end="arrive_dt",
            y="vessvoy",
            color="OriginPortCode",
            hover_data=["DestPortCode", "Vessel_Name"]
        )

        fig_g.update_yaxes(autorange="reversed")
        fig_g = apply_strict_dark_theme(fig_g)

        st.plotly_chart(fig_g, use_container_width=True)

    else:
        st.warning("No valid timeline data available.")
      # ===============================
# INTERPRETATION: VOYAGE SCHEDULE
# ===============================
if not gantt_df.empty:

    durations = (
        gantt_df["arrive_dt"] -
        gantt_df["final_depart"]
    ).dt.total_seconds() / 3600

    long_ratio = (durations > durations.quantile(0.95)).mean()

    overlap_count = 0
    for vv, group in gantt_df.groupby("vessvoy"):
        group = group.sort_values("final_depart")
        overlap_count += (
            group["final_depart"].shift(-1) <
            group["arrive_dt"]
        ).sum()

    if overlap_count > 0:
        st.warning(
            f"⚠️ **Schedule Overlaps Detected**\n\n"
            f"{overlap_count} overlapping voyage windows found. "
            "This may indicate data quality issues or unrealistic scheduling."
        )
    elif long_ratio > 0.15:
        st.warning(
            "⚠️ **Extended Voyage Durations Observed**\n\n"
            "Some voyages are significantly longer than typical sailing windows."
        )
    else:
        st.success(
            "✅ **Voyage Scheduling Looks Consistent**\n\n"
            "No major overlaps or abnormal durations detected."
        )



