# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(layout="wide", page_title="Matson Schedule Data Analysis")

# ===============================
# LOAD DATA
# ===============================
DATA_FILE = os.path.join("data", "shipping_schedule_enriched.csv")

if not os.path.exists(DATA_FILE):
    st.error("Data file not found in /data folder")
    st.stop()

df = pd.read_csv(DATA_FILE)

if df.empty:
    st.error("Data file is empty")
    st.stop()

# ===============================
# STANDARDIZE COLUMN NAMES
# ===============================
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)
# Normalize column names
df.columns = df.columns.str.strip().str.lower()

# Create final_depart if departure column exists
if "depart_dt" in df.columns:
    df["final_depart"] = pd.to_datetime(df["depart_dt"], errors="coerce")

elif "departure_date" in df.columns:
    df["final_depart"] = pd.to_datetime(df["departure_date"], errors="coerce")

elif "departure" in df.columns:
    df["final_depart"] = pd.to_datetime(df["departure"], errors="coerce")

else:
    st.warning("No departure column found in dataset.")


# ===============================
# SAFE DATE CONVERSION
# ===============================
for col in ["arrive_dt", "final_depart"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# ===============================
# CLEAN STRING COLUMNS
# ===============================
string_cols = [
    "vessel_name",
    "voyage",
    "bound",
    "originportcode",
    "destportcode"
]

for col in string_cols:
    if col in df.columns:
        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

df.replace("nan", "", inplace=True)

# ===============================
# BUILD SAFE VESSEL-VOYAGE
# ===============================
if "voyage" in df.columns:
    df["vessvoy"] = np.where(
        df["voyage"] != "",
        df["vessel_name"] + "*" + df["voyage"] + "*" + df.get("bound", ""),
        df["vessel_name"] + "*NO_VOYAGE"
    )
else:
    df["vessvoy"] = df.get("vessel_name", "UNKNOWN")

# ===============================
# SIDEBAR FILTERS
# ===============================
st.sidebar.header("Filters")

date_range = st.sidebar.date_input(
    "Arrival date range",
    [
        df["arrive_dt"].min().date(),
        df["arrive_dt"].max().date()
    ]
)

vessels = st.sidebar.multiselect(
    "Vessel",
    sorted(df["vessel_name"].unique())
)

voyages = st.sidebar.multiselect(
    "Voyage",
    sorted(df["vessvoy"].unique())
)

origins = st.sidebar.multiselect(
    "Origin",
    sorted(df["originportcode"].unique())
)

dests = st.sidebar.multiselect(
    "Destination",
    sorted(df["destportcode"].unique())
)

# ===============================
# APPLY FILTERS
# ===============================
df_f = df.copy()

if date_range and len(date_range) == 2:
    start, end = date_range
    df_f = df_f[
        (df_f["arrive_dt"] >= pd.to_datetime(start)) &
        (df_f["arrive_dt"] <= pd.to_datetime(end) + pd.Timedelta(days=1))
    ]

if vessels:
    df_f = df_f[df_f["vessel_name"].isin(vessels)]

if voyages:
    df_f = df_f[df_f["vessvoy"].isin(voyages)]

if origins:
    df_f = df_f[df_f["originportcode"].isin(origins)]

if dests:
    df_f = df_f[df_f["destportcode"].isin(dests)]
    
st.write("Filtered rows:", len(df_f))
st.write("Non-null departure:", df_f["final_depart"].notna().sum() if "final_depart" in df_f.columns else "No column")
st.write("Non-null arrival:", df_f["arrive_dt"].notna().sum())
st.write("Non-null transit:", df_f["transit_hours"].notna().sum() if "transit_hours" in df_f.columns else "No column")

# ===============================
# KPIs
# ===============================
if "transit_hours" in df_f.columns:
    avg_transit = df_f["transit_hours"].mean()
else:
    avg_transit = np.nan

c1, c2, c3, c4 = st.columns(4)

c1.metric("Rows Count", f"{len(df_f):,}")
c2.metric("Unique Vessels", df_f["vessel_name"].nunique())
c3.metric("Unique Voyages", df_f["vessvoy"].nunique())
c4.metric(
    "Avg Transit (hrs)",
    f"{avg_transit:.1f}" if not np.isnan(avg_transit) else "N/A"
)

# ===============================
# DEPARTURE TREND
# ===============================
st.subheader("Departure Count by Date")

if "final_depart" in df_f.columns:

    dep_source = df_f["final_depart"].dropna()

    if not dep_source.empty:

        dep = (
            dep_source
            .dt.date
            .value_counts()
            .sort_index()
            .reset_index()
        )

        dep.columns = ["date", "count"]

        fig_dep = px.line(dep, x="date", y="count", markers=True)
        fig_dep.update_layout(
            xaxis_title="Date",
            yaxis_title="Departure Count"
        )

        st.plotly_chart(apply_dark(fig_dep), use_container_width=True)

    else:
        st.info("No departure data available for selected filters.")

else:
    st.warning("Column 'final_depart' not found in dataset.")

# ===============================
# TOP PORTS
# ===============================
st.subheader("Top Origin & Destination Ports")

if "originportcode" in df_f.columns:
    top_o = df_f["originportcode"].value_counts().head(15).reset_index()
    top_o.columns = ["port", "count"]
    fig_o = px.bar(top_o, x="count", y="port", orientation="h")
    st.plotly_chart(fig_o, use_container_width=True)

if "destportcode" in df_f.columns:
    top_d = df_f["destportcode"].value_counts().head(15).reset_index()
    top_d.columns = ["port", "count"]
    fig_d = px.bar(top_d, x="count", y="port", orientation="h")
    st.plotly_chart(fig_d, use_container_width=True)

# ===============================
# SCATTER
# ===============================
st.subheader("Transit Hours vs Port Call Index")

if {"transit_hours", "port_call_index"}.issubset(df_f.columns):

    sc = df_f.dropna(subset=["transit_hours", "port_call_index"])

    if not sc.empty:

        fig_sc = px.scatter(
            sc,
            x="port_call_index",
            y="transit_hours",
            color="originportcode"
        )

        fig_sc.update_layout(
            xaxis_title="Port Call Index",
            yaxis_title="Transit Hours"
        )

        st.plotly_chart(fig_sc, use_container_width=True)


    else:
        st.info("No transit data available for selected filters.")

else:
    st.warning("Transit fields missing in dataset.")

# ===============================
# GANTT
# ===============================
st.subheader("Voyage Timeline (Gantt)")

required_cols = {"vessvoy", "final_depart", "arrive_dt", "originportcode"}

if required_cols.issubset(df_f.columns):

    gantt_df = df_f.dropna(subset=["final_depart", "arrive_dt"])

    if not gantt_df.empty:

        fig_g = px.timeline(
            gantt_df,
            x_start="final_depart",
            x_end="arrive_dt",
            y="vessvoy",
            color="originportcode"
        )

        fig_g.update_yaxes(autorange="reversed")
        st.plotly_chart(fig_g, use_container_width=True)

    else:
        st.info("No valid voyage timeline data.")

else:
    st.warning("Required columns missing for Gantt chart.")
