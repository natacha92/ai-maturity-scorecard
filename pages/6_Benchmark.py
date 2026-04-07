import streamlit as st
import pandas as pd
from models.database import init_db, get_session, Client
from engine.benchmark import (
    get_all_completed_assessments, benchmark_by_sector, benchmark_by_size,
    get_client_ranking, get_client_history, compute_percentile,
)
from utils.charts import (
    benchmark_comparison_chart, radar_chart, timeline_chart, domain_bar_chart,
)

init_db()

st.title("Benchmark & Comparison")

# Load all completed assessments
assessments = get_all_completed_assessments()

if len(assessments) < 1:
    st.info("At least 1 completed assessment is needed for benchmarking.")
    st.stop()

# --- Overview ---
st.subheader("Overview")
col1, col2, col3 = st.columns(3)
col1.metric("Total Assessments", len(assessments))
col2.metric("Unique Clients", len(set(a["client_id"] for a in assessments)))
col3.metric("Avg. Global Score", f"{sum(a['global_score'] for a in assessments) / len(assessments):.1f}%")

# --- Client Comparison ---
st.divider()
st.subheader("Client Comparison")

client_names = list(set(a["client_name"] for a in assessments))
if len(client_names) >= 2:
    selected_clients = st.multiselect(
        "Select clients to compare",
        client_names,
        default=client_names[:min(4, len(client_names))],
    )

    if selected_clients:
        # Get latest assessment per client
        compare_data = []
        for name in selected_clients:
            client_assessments = [a for a in assessments if a["client_name"] == name]
            latest = max(client_assessments, key=lambda a: a["created_at"])
            compare_data.append(latest)

        st.plotly_chart(
            benchmark_comparison_chart(compare_data, "Domain Score Comparison"),
            use_container_width=True,
        )

        # Ranking table
        df = pd.DataFrame([
            {
                "Client": a["client_name"],
                "Sector": a["sector"],
                "Size": a["size"],
                "Global Score": f"{a['global_score']}%",
                "Level": a["maturity_level"]["label"],
            }
            for a in sorted(compare_data, key=lambda x: -x["global_score"])
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Add more clients and complete assessments to enable comparison.")

# --- Sector Benchmark ---
st.divider()
st.subheader("Sector Benchmark")

sector_data = benchmark_by_sector(assessments)
if sector_data:
    sector_df = pd.DataFrame([
        {
            "Sector": sector,
            "Clients": data["count"],
            "Avg Score": f"{data['avg_global']}%",
            **{f"{d}": f"{s}%" for d, s in data["avg_domains"].items()},
        }
        for sector, data in sector_data.items()
    ])
    st.dataframe(sector_df, use_container_width=True, hide_index=True)

    # Bar chart of sector averages
    sector_scores = {s: d["avg_global"] for s, d in sector_data.items()}
    st.plotly_chart(
        domain_bar_chart(sector_scores, "Average Score by Sector"),
        use_container_width=True,
    )

# --- Size Benchmark ---
st.divider()
st.subheader("Company Size Benchmark")

size_data = benchmark_by_size(assessments)
if size_data:
    size_df = pd.DataFrame([
        {
            "Size": size,
            "Clients": data["count"],
            "Avg Score": f"{data['avg_global']}%",
            **{f"{d}": f"{s}%" for d, s in data["avg_domains"].items()},
        }
        for size, data in size_data.items()
    ])
    st.dataframe(size_df, use_container_width=True, hide_index=True)

# --- Client History ---
st.divider()
st.subheader("Score Evolution (Year-over-Year)")

session = get_session()
try:
    all_clients = session.query(Client).order_by(Client.name).all()
    client_map = {c.id: c.name for c in all_clients}
finally:
    session.close()

clients_with_history = set()
for a in assessments:
    clients_with_history.add(a["client_name"])

if clients_with_history:
    selected_history_client = st.selectbox(
        "Select client for history",
        sorted(clients_with_history),
    )

    # Find client ID
    client_id = None
    for a in assessments:
        if a["client_name"] == selected_history_client:
            client_id = a["client_id"]
            break

    if client_id:
        history = get_client_history(client_id, assessments)
        if len(history) > 1:
            st.plotly_chart(
                timeline_chart(history, f"Score Evolution — {selected_history_client}"),
                use_container_width=True,
            )
        else:
            st.info("Only one assessment found. Complete more assessments over time to see evolution.")

        # Percentile ranking
        ranking = get_client_ranking(client_id, assessments)
        if ranking:
            col1, col2, col3 = st.columns(3)
            col1.metric("Global Score", f"{ranking['global_score']}%")
            col2.metric("Rank", f"#{ranking['rank']} / {ranking['total']}")
            col3.metric("Percentile", f"Top {100 - ranking['percentile']:.0f}%")
