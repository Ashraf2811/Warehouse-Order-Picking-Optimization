import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Warehouse Order Picking Optimization",
    page_icon="📦",
    layout="wide",
)

SUMMARY_FILE = "optimized_wave_summary.csv"
LOCATIONS_FILE = "optimized_wave_locations.csv"


@st.cache_data
def load_data():
    summary = pd.read_csv(SUMMARY_FILE)
    locations = pd.read_csv(LOCATIONS_FILE)

    summary["recommended_wave"] = pd.to_numeric(
        summary["recommended_wave"], errors="coerce"
    ).astype("Int64")

    locations["recommended_wave"] = pd.to_numeric(
        locations["recommended_wave"], errors="coerce"
    ).astype("Int64")

    for col in ["total_workload", "unique_locations", "spatial_spread", "utilization"]:
        summary[col] = pd.to_numeric(summary[col], errors="coerce")

    for col in ["x", "y", "z", "assigned_units"]:
        locations[col] = pd.to_numeric(locations[col], errors="coerce")

    return summary, locations


def fmt_num(value, decimals=2):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}"


try:
    wave_summary, wave_locations = load_data()
except FileNotFoundError as exc:
    st.error(
        "Required CSV file not found. Make sure these files are in the same "
        "GitHub repository folder as app.py:\n\n"
        "• optimized_wave_summary.csv\n"
        "• optimized_wave_locations.csv"
    )
    st.stop()
except Exception as exc:
    st.error(f"Could not load the project data: {exc}")
    st.stop()


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------
st.sidebar.title("📦 Warehouse Optimization")
st.sidebar.caption("V3.1 Proximity-Constrained Wave Optimization")

st.sidebar.markdown("### Filters")

min_wave = int(wave_summary["recommended_wave"].min())
max_wave = int(wave_summary["recommended_wave"].max())

wave_range = st.sidebar.slider(
    "Recommended wave range",
    min_value=min_wave,
    max_value=max_wave,
    value=(min_wave, max_wave),
)

workload_range = st.sidebar.slider(
    "Workload (units)",
    min_value=int(wave_summary["total_workload"].min()),
    max_value=int(wave_summary["total_workload"].max()),
    value=(
        int(wave_summary["total_workload"].min()),
        int(wave_summary["total_workload"].max()),
    ),
)

spread_range = st.sidebar.slider(
    "Spatial spread",
    min_value=float(wave_summary["spatial_spread"].min()),
    max_value=float(wave_summary["spatial_spread"].max()),
    value=(
        float(wave_summary["spatial_spread"].min()),
        float(wave_summary["spatial_spread"].max()),
    ),
)

filtered_summary = wave_summary[
    wave_summary["recommended_wave"].between(*wave_range)
    & wave_summary["total_workload"].between(*workload_range)
    & wave_summary["spatial_spread"].between(*spread_range)
].copy()

filtered_locations = wave_locations[
    wave_locations["recommended_wave"].isin(
        filtered_summary["recommended_wave"].dropna().astype(int)
    )
].copy()


# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------
st.title("📦 Warehouse Order Picking Efficiency Optimization")
st.markdown(
    """
This dashboard presents the final **V3.1 proximity-constrained optimization**
results from the warehouse order-picking project.

The optimized waves aim to keep workload at approximately **24 units**, never
exceed **25 units**, limit the contribution from one warehouse location to
**12 units per wave**, and keep consecutive picking locations spatially close.
"""
)

st.info(
    "The dashboard uses the final CSV outputs from the notebook. "
    "It does not retrain or rerun the optimization algorithm."
)


# -------------------------------------------------------------------
# KPI section
# -------------------------------------------------------------------
total_waves = len(wave_summary)
avg_workload = wave_summary["total_workload"].mean()
avg_utilization = wave_summary["utilization"].mean()
avg_locations = wave_summary["unique_locations"].mean()
avg_spread = wave_summary["spatial_spread"].mean()
total_units = wave_locations["assigned_units"].sum()

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Optimized Waves", f"{total_waves:,}")
k2.metric("Assigned Units", f"{int(total_units):,}")
k3.metric("Avg Workload", fmt_num(avg_workload))
k4.metric("Avg Utilization", f"{avg_utilization:.2f}%")
k5.metric("Avg Locations / Wave", fmt_num(avg_locations))
k6.metric("Avg Spatial Spread", fmt_num(avg_spread))


# -------------------------------------------------------------------
# Tabs
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Overview", "🔎 Wave Explorer", "📍 Warehouse Locations", "📄 Data"]
)


with tab1:
    st.subheader("Optimization Performance")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Workload distribution")
        workload_counts = (
            wave_summary["total_workload"]
            .value_counts()
            .sort_index()
            .rename_axis("Workload")
            .to_frame("Waves")
        )
        st.bar_chart(workload_counts)

    with c2:
        st.markdown("#### Utilization distribution")
        utilization_bins = pd.cut(
            wave_summary["utilization"],
            bins=[0, 80, 90, 95, 100.01],
            labels=["≤80%", "80–90%", "90–95%", "95–100%"],
            include_lowest=True,
        )
        utilization_counts = (
            utilization_bins.value_counts()
            .reindex(["≤80%", "80–90%", "90–95%", "95–100%"])
            .fillna(0)
            .astype(int)
            .rename_axis("Utilization")
            .to_frame("Waves")
        )
        st.bar_chart(utilization_counts)

    st.markdown("#### Spatial spread")
    spread_chart = (
        wave_summary[["recommended_wave", "spatial_spread"]]
        .set_index("recommended_wave")
        .sort_index()
    )
    st.line_chart(spread_chart)

    st.markdown("#### Final optimization interpretation")

    i1, i2, i3 = st.columns(3)

    with i1:
        st.metric(
            "Waves at 24–25 units",
            f"{wave_summary['total_workload'].between(24, 25).sum():,}",
        )

    with i2:
        st.metric(
            "Waves > 50 spread",
            f"{(wave_summary['spatial_spread'] > 50).sum():,}",
        )

    with i3:
        st.metric(
            "Waves > 100 spread",
            f"{(wave_summary['spatial_spread'] > 100).sum():,}",
        )

    st.caption(
        "The notebook reports that the optimization reorganizes coordinate-valid "
        "picking work into fewer, better-utilized, geographically concentrated waves."
    )


with tab2:
    st.subheader("Recommended Wave Explorer")

    if filtered_summary.empty:
        st.warning("No waves match the selected filters.")
    else:
        selected_wave = st.selectbox(
            "Select a recommended wave",
            filtered_summary["recommended_wave"].dropna().astype(int).tolist(),
        )

        selected_summary = filtered_summary[
            filtered_summary["recommended_wave"] == selected_wave
        ].iloc[0]

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Workload", f"{int(selected_summary['total_workload'])} units")
        s2.metric("Utilization", f"{selected_summary['utilization']:.2f}%")
        s3.metric("Unique Locations", int(selected_summary["unique_locations"]))
        s4.metric("Spatial Spread", fmt_num(selected_summary["spatial_spread"]))

        selected_locations = filtered_locations[
            filtered_locations["recommended_wave"] == selected_wave
        ].copy()

        st.markdown("#### Location assignments")
        st.dataframe(
            selected_locations[
                [
                    "recommended_wave",
                    "originalLocation",
                    "x",
                    "y",
                    "z",
                    "assigned_units",
                ]
            ].sort_values(["z", "y", "x"]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### 2D warehouse position")
        if not selected_locations.empty:
            chart_data = selected_locations[["x", "y", "assigned_units"]].copy()
            chart_data = chart_data.rename(
                columns={"assigned_units": "Assigned Units"}
            )
            st.scatter_chart(
                chart_data,
                x="x",
                y="y",
                size="Assigned Units",
                use_container_width=True,
            )


with tab3:
    st.subheader("Warehouse Location Analysis")

    location_summary = (
        filtered_locations.groupby("originalLocation")
        .agg(
            assigned_units=("assigned_units", "sum"),
            waves=("recommended_wave", "nunique"),
            x=("x", "first"),
            y=("y", "first"),
            z=("z", "first"),
        )
        .reset_index()
        .sort_values("assigned_units", ascending=False)
    )

    l1, l2, l3 = st.columns(3)
    l1.metric("Unique Locations", f"{location_summary.shape[0]:,}")
    l2.metric(
        "Location Assignment Records",
        f"{filtered_locations.shape[0]:,}",
    )
    l3.metric(
        "Assigned Units",
        f"{int(filtered_locations['assigned_units'].sum()):,}",
    )

    st.markdown("#### Most utilized warehouse locations")
    st.dataframe(
        location_summary.head(25),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Location workload")
    top_locations = (
        location_summary.head(30)
        .set_index("originalLocation")[["assigned_units"]]
        .sort_values("assigned_units")
    )
    st.bar_chart(top_locations)


with tab4:
    st.subheader("Final Dataset Preview")

    st.markdown("#### Optimized wave summary")
    st.dataframe(
        filtered_summary.head(500),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Optimized wave locations")
    st.dataframe(
        filtered_locations.head(500),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "⬇️ Download filtered wave summary",
        data=filtered_summary.to_csv(index=False).encode("utf-8"),
        file_name="filtered_wave_summary.csv",
        mime="text/csv",
    )

    st.download_button(
        "⬇️ Download filtered location assignments",
        data=filtered_locations.to_csv(index=False).encode("utf-8"),
        file_name="filtered_wave_locations.csv",
        mime="text/csv",
    )


# -------------------------------------------------------------------
# Footer
# -------------------------------------------------------------------
st.divider()
st.caption(
    "Warehouse Order Picking Efficiency Optimization | Final V3.1 results"
)
st.caption(
    "Important limitation: the notebook states that spatial optimization "
    "covered 191,583 of 215,192 picking units (89.03%). "
    "The remaining 23,609 units lacked complete warehouse coordinates."
)
