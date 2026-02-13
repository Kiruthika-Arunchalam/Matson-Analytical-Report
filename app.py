# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(
    layout="wide",
    page_title="Matson Schedule Data Analysis"
)

# ===============================
# GLOBAL DARK CSS (METRICS + HEADERS)
# ===============================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0b0b0b;
        color: #ffffff;
    }

    section[data-testid="stSidebar"] {
        background-color: #0b0b0b;
    }

    /* Sidebar labels */
    section[data-testid="stSidebar"] label {
        color: #8ecae6 !important;
        font-weight: 600;
    }

    /* Sidebar headers */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #8ecae6 !important;
        font-weight: 700;
    }

    /* Metric cards */
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

    /* Main headers */
    h1 {
        color: #669bbc!important;
        font-weight: 800 !important;
    }

    h2 {
        color: #d4a373 !important;
        font-weight: 700 !important;
    }

    h3 {
        color: #d4a373 !important;
        font-weight: 700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ===============================
# PLOTLY STRICT DARK THEME
# ===============================
def apply_strict_dark_theme(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="white", size=14),
        title=dict(font=dict(color="white", size=18)),
        legend=dict(font=dict(color="white")),
    )

    fig.update_xaxes(
        title_font=dict(color="white", size=14),
        tickfont=dict(color="white", size=12),
        gridcolor="rgba(255,255,255,0.15)"
    )

    fig.update_yaxes(
        title_font=dict(color="white", size=14),
        tickfont=dict(color="white", size=12),
        gridcolor="rgba(255,255,255,0.15)"
    )
    return fig

# ===============================
# LOAD DATA (BACKEND ONLY)
# ===============================
#DATA_FILE = r"C:\Users\sm2069\Desktop\Matson_Data-Analytics\shipping_schedule_enriched.csv"
import os

DATA_FILE = os.path.join("data", "shipping_schedule_enriched.csv")

if not os.path.exists(DATA_FILE):
    st.error("Data file not found on server")
    st.stop()

df = pd.read_csv(DATA_FILE)

if df.empty:
    st.error("Data file loaded but contains no records")
    st.stop()


df.columns = df.columns.str.strip()

# ===============================
# DATE PARSING
# ===============================
df["arrive_dt"] = pd.to_datetime(df["arrive_dt"], errors="coerce")
df["final_depart"] = pd.to_datetime(
    df.get("final_imputed_depart_dt", df.get("depart_dt")),
    errors="coerce"
)

# ===============================
# DERIVED FIELDS
# ===============================
df["vessvoy"] = (
    df["Vessel_Name"].astype(str) + "*" +
    df["Voyage"].astype(str) + "*" +
    df["Bound"].astype(str)
)

df["port_call_index"] = df.groupby("vessvoy").cumcount() + 1
df["transit_hours_final"] = (
    df["arrive_dt"] - df["final_depart"]
).dt.total_seconds() / 3600

# ===============================
# SIDEBAR FILTERS
# ===============================
st.sidebar.header("Filters")

date_range = st.sidebar.date_input(
    "Arrival date range",
    [df["arrive_dt"].min().date(), df["arrive_dt"].max().date()]
)

vessels = st.sidebar.multiselect(
    "Vessel Name",
    sorted(df["Vessel_Name"].dropna().unique())
)

voyage_filter = st.sidebar.multiselect(
    "Voyage (vessvoy)",
    sorted(df["vessvoy"].dropna().unique())
)

origin_filter = st.sidebar.multiselect(
    "Origin Port",
    sorted(df["OriginPortCode"].dropna().unique())
)

dest_filter = st.sidebar.multiselect(
    "Destination Port",
    sorted(df["DestPortCode"].dropna().unique())
)

# ===============================
# APPLY FILTERS
# ===============================
df_f = df.copy()

df_f = df_f[
    (df_f["arrive_dt"] >= pd.to_datetime(date_range[0])) &
    (df_f["arrive_dt"] <= pd.to_datetime(date_range[1]) + pd.Timedelta(days=1))
]

if vessels:
    df_f = df_f[df_f["Vessel_Name"].isin(vessels)]

if voyage_filter:
    df_f = df_f[df_f["vessvoy"].isin(voyage_filter)]

if origin_filter:
    df_f = df_f[df_f["OriginPortCode"].isin(origin_filter)]

if dest_filter:
    df_f = df_f[df_f["DestPortCode"].isin(dest_filter)]

# ===============================
# TITLE
# ===============================
st.title("Matson Schedule Data Analysis Report")

# ===============================
# KPIs
# ===============================
st.header("Overview & Charts")
k1, k2, k3, k4 = st.columns(4)

k1.metric("Rows Count", f"{len(df_f):,}")
k2.metric("Unique Voyages", f"{df_f['vessvoy'].nunique():,}")
k3.metric("Unique Vessel Name", f"{df_f['Vessel_Name'].nunique():,}")

avg_transit = df_f["transit_hours_final"].mean()
k4.metric("Avg Transit (hrs)", f"{avg_transit:.1f}" if not np.isnan(avg_transit) else "N/A")

# ===============================
# DEPART DATE DISTRIBUTION
# ===============================
st.subheader("Depart Date Distribution")

dep_counts = (
    df_f["final_depart"]
    .dropna()
    .dt.date
    .value_counts()
    .sort_index()
    .reset_index()
)
dep_counts.columns = ["date", "count"]

fig = px.line(dep_counts, x="date", y="count", markers=True)
fig = apply_strict_dark_theme(fig)
st.plotly_chart(fig, width="stretch")

# -------- Interpretation: Depart Date Distribution --------
with st.container():
    counts = dep_counts["count"]
    mean_c = counts.mean()
    std_c = counts.std()
    max_c = counts.max()

    if max_c > mean_c + 3 * std_c:
        st.warning(
            "⚠️ **Anomalous departure pattern detected**. "
            "Certain departure dates occur far more frequently than others. "
            "This often indicates reused or default departure dates in the schedule data."
        )
    elif std_c / mean_c > 0.7:
        st.info(
            "ℹ️ **High variability observed**. "
            "Departure activity fluctuates significantly across dates, "
            "which may reflect seasonal planning or uneven service deployment."
        )
    else:
        st.success(
            "✅ **Normal distribution**. "
            "Departures are well spread over time with no abnormal clustering."
        )


# ===============================
# TOP ORIGIN PORTS
# ===============================
st.subheader("Top Origin & Destination Ports")

col1, col2 = st.columns(2)

with col1:
    top_o = (
        df_f["OriginPortCode"]
        .value_counts()
        .head(15)
        .reset_index()
    )
    top_o.columns = ["OriginPortCode", "count"]

    fig_o = px.bar(
        top_o,
        x="count",
        y="OriginPortCode",
        orientation="h",
        title="Top Origin Ports"
    )
    fig_o = apply_strict_dark_theme(fig_o)
    st.plotly_chart(fig_o, use_container_width=True)

with col2:
    top_d = (
        df_f["DestPortCode"]
        .value_counts()
        .head(15)
        .reset_index()
    )
    top_d.columns = ["DestPortCode", "count"]

    fig_d = px.bar(
        top_d,
        x="count",
        y="DestPortCode",
        orientation="h",
        title="Top Destination Ports"
    )
    fig_d = apply_strict_dark_theme(fig_d)
    st.plotly_chart(fig_d, use_container_width=True)
    # -------- Interpretation: Port Concentration --------
with st.container():
    total_rows = len(df_f)
    top_origin_share = top_o["count"].iloc[0] / total_rows if not top_o.empty else 0
    top_dest_share = top_d["count"].iloc[0] / total_rows if not top_d.empty else 0

    if top_origin_share > 0.6 or top_dest_share > 0.6:
        st.warning(
            "⚠️ **High port concentration risk**. "
            "A single port dominates movements, which increases operational dependency "
            "and risk exposure to local disruptions."
        )
    elif top_origin_share > 0.35 or top_dest_share > 0.35:
        st.info(
            "ℹ️ **Moderate concentration detected**. "
            "A few ports handle most of the traffic, "
            "which is typical for hub-and-spoke shipping models."
        )
    else:
        st.success(
            "✅ **Well-distributed port network**. "
            "Traffic is spread across multiple origins and destinations."
        )


# ===============================
# SCATTER: TRANSIT VS PORT CALL
# ===============================
st.subheader("Transit Hours vs Port Call Index")

sc = df_f.dropna(subset=["transit_hours_final", "port_call_index"])

fig_sc = px.scatter(
    sc,
    x="port_call_index",
    y="transit_hours_final",
    color="OriginPortCode",
    hover_data=["Vessel_Name", "DestPortCode"]
)
fig_sc = apply_strict_dark_theme(fig_sc)
st.plotly_chart(fig_sc, use_container_width=True)
# -------- Interpretation: Transit vs Port Call Index --------
with st.container():
    corr = sc[["port_call_index", "transit_hours_final"]].corr().iloc[0, 1]
    outlier_ratio = (sc["transit_hours_final"] >
                     sc["transit_hours_final"].quantile(0.95)).mean()

    if corr > 0.6:
        st.warning(
            "⚠️ **Cascading delay pattern detected**. "
            "Transit time increases with later port calls, "
            "suggesting delays accumulate along the voyage."
        )
    elif corr < -0.5:
        st.info(
            "ℹ️ **Improving transit efficiency**. "
            "Later port calls tend to have shorter transit times, "
            "possibly due to optimized routing."
        )
    elif outlier_ratio > 0.1:
        st.warning(
            "⚠️ **Significant outliers present**. "
            "A notable portion of port calls experience unusually long transit times."
        )
    else:
        st.success(
            "✅ **Stable transit behavior**. "
            "Transit durations remain consistent throughout the voyage sequence."
        )


# ===============================
# GANTT TIMELINE
# ===============================
st.subheader("Voyage Timeline (Gantt)")

vv_select = st.multiselect(
    "Select voyages (max 10)",
    sorted(df_f["vessvoy"].unique()),
    default=sorted(df_f["vessvoy"].unique())[:5]
)

gantt_df = df_f[df_f["vessvoy"].isin(vv_select)]

fig_g = px.timeline(
    gantt_df,
    x_start="final_depart",
    x_end="arrive_dt",
    y="vessvoy",
    color="OriginPortCode"
)
fig_g.update_yaxes(autorange="reversed")
fig_g = apply_strict_dark_theme(fig_g)
st.plotly_chart(fig_g, use_container_width=True)

# ===============================
# DATA PREVIEW
# ===============================
#st.subheader("Data Preview")
#st.dataframe(df_f.head(200))

# ===============================
# DOWNLOAD
# ===============================
#st.download_button(
   # "Download Filtered CSV",
   # df_f.to_csv(index=False),
   # file_name="shipping_schedule_filtered.csv",
   # mime="text/csv"
#)

#st.success("Dashboard loaded successfully 🚢")
