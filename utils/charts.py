"""Reusable Plotly chart builders for PAIMS."""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Color palette
COLORS = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "warning": "#ff7f0e",
    "danger": "#d62728",
    "info": "#17becf",
    "muted": "#7f7f7f",
}

MATURITY_COLORS = {
    "Initial": "#d62728",
    "Structured": "#ff7f0e",
    "Deployed": "#2ca02c",
    "Advanced": "#1f77b4",
}

DOMAIN_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
]


def score_color(score):
    if score <= 30:
        return MATURITY_COLORS["Initial"]
    elif score <= 60:
        return MATURITY_COLORS["Structured"]
    elif score <= 80:
        return MATURITY_COLORS["Deployed"]
    return MATURITY_COLORS["Advanced"]


def radar_chart(domain_scores, title="AI Maturity Radar"):
    """Create a radar/spider chart of domain scores."""
    domains = list(domain_scores.keys())
    scores = list(domain_scores.values())
    # Close the polygon
    domains_closed = domains + [domains[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=scores_closed,
        theta=domains_closed,
        fill="toself",
        fillcolor="rgba(31, 119, 180, 0.2)",
        line=dict(color=COLORS["primary"], width=2),
        name="Current",
    ))

    # Target overlay
    target = [70] * len(domains) + [70]
    fig.add_trace(go.Scatterpolar(
        r=target,
        theta=domains_closed,
        fill=None,
        line=dict(color=COLORS["muted"], width=1, dash="dash"),
        name="Target (70%)",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickvals=[25, 50, 75, 100]),
        ),
        showlegend=True,
        title=title,
        height=450,
        margin=dict(t=60, b=30),
    )
    return fig


def gauge_chart(score, title="Global Score", height=250):
    """Create a gauge chart for a single score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": title, "font": {"size": 16}},
        number={"suffix": "%", "font": {"size": 28}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": score_color(score)},
            "steps": [
                {"range": [0, 30], "color": "rgba(214, 39, 40, 0.1)"},
                {"range": [30, 60], "color": "rgba(255, 127, 14, 0.1)"},
                {"range": [60, 80], "color": "rgba(44, 160, 44, 0.1)"},
                {"range": [80, 100], "color": "rgba(31, 119, 180, 0.1)"},
            ],
            "threshold": {
                "line": {"color": COLORS["muted"], "width": 2},
                "thickness": 0.75,
                "value": 70,
            },
        },
    ))
    fig.update_layout(height=height, margin=dict(t=40, b=10, l=30, r=30))
    return fig


def domain_bar_chart(domain_scores, title="Score by Domain"):
    """Horizontal bar chart of domain scores."""
    domains = list(domain_scores.keys())
    scores = list(domain_scores.values())
    colors = [score_color(s) for s in scores]

    fig = go.Figure(go.Bar(
        x=scores,
        y=domains,
        orientation="h",
        marker_color=colors,
        text=[f"{s:.0f}%" for s in scores],
        textposition="auto",
    ))

    # Target line
    fig.add_vline(x=70, line_dash="dash", line_color=COLORS["muted"],
                  annotation_text="Target", annotation_position="top")

    fig.update_layout(
        title=title,
        xaxis=dict(range=[0, 100], title="Score (%)"),
        yaxis=dict(autorange="reversed"),
        height=max(300, len(domains) * 50 + 80),
        margin=dict(t=50, b=30, l=150),
    )
    return fig


def heatmap_chart(subdomain_scores, title="Maturity Heatmap"):
    """
    Heatmap of domain × subdomain scores.
    subdomain_scores: {domain: {subdomain: score}}
    """
    domains = []
    subdomains = []
    scores = []

    for domain, subs in subdomain_scores.items():
        for sub, score in subs.items():
            domains.append(domain)
            subdomains.append(sub)
            scores.append(score)

    df = pd.DataFrame({"Domain": domains, "Subdomain": subdomains, "Score": scores})
    pivot = df.pivot(index="Domain", columns="Subdomain", values="Score")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[
            [0, "#d62728"],
            [0.3, "#ff7f0e"],
            [0.6, "#ffdd57"],
            [0.8, "#2ca02c"],
            [1.0, "#1f77b4"],
        ],
        zmin=0,
        zmax=100,
        text=[[f"{v:.0f}%" if pd.notna(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont={"size": 12},
        colorbar=dict(title="Score"),
    ))

    fig.update_layout(
        title=title,
        height=max(300, len(pivot.index) * 60 + 100),
        margin=dict(t=50, b=50, l=150),
    )
    return fig


def gap_chart(gaps, title="Gap Analysis — Current vs Target"):
    """
    Horizontal bar chart showing current score and gap to target.
    gaps: {domain: {current, target, gap}}
    """
    domains = list(gaps.keys())
    current = [gaps[d]["current"] for d in domains]
    gap_vals = [max(0, gaps[d]["gap"]) for d in domains]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=domains, x=current, orientation="h",
        name="Current Score",
        marker_color=COLORS["primary"],
        text=[f"{c:.0f}%" for c in current],
        textposition="auto",
    ))

    fig.add_trace(go.Bar(
        y=domains, x=gap_vals, orientation="h",
        name="Gap to Target",
        marker_color="rgba(214, 39, 40, 0.4)",
        text=[f"+{g:.0f}%" for g in gap_vals],
        textposition="auto",
    ))

    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis=dict(range=[0, 100], title="Score (%)"),
        yaxis=dict(autorange="reversed"),
        height=max(300, len(domains) * 50 + 80),
        margin=dict(t=50, b=30, l=150),
    )
    return fig


def benchmark_comparison_chart(assessments, title="Client Comparison"):
    """
    Grouped bar chart comparing multiple clients' domain scores.
    assessments: list of {client_name, domain_scores: {domain: score}}
    """
    data = []
    for a in assessments:
        for domain, score in a["domain_scores"].items():
            data.append({
                "Client": a["client_name"],
                "Domain": domain,
                "Score": score,
            })

    df = pd.DataFrame(data)
    fig = px.bar(
        df, x="Domain", y="Score", color="Client",
        barmode="group", title=title,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        yaxis=dict(range=[0, 100], title="Score (%)"),
        height=400,
        margin=dict(t=50, b=80),
    )
    return fig


def timeline_chart(history, title="Score Evolution"):
    """
    Line chart showing score evolution over time.
    history: list of {created_at, global_score, domain_scores}
    """
    if not history:
        return go.Figure().update_layout(title="No historical data")

    dates = [h["created_at"] for h in history]
    globals_ = [h["global_score"] for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=globals_,
        mode="lines+markers",
        name="Global Score",
        line=dict(color=COLORS["primary"], width=3),
    ))

    # Domain lines
    all_domains = list(history[0].get("domain_scores", {}).keys())
    for i, domain in enumerate(all_domains):
        domain_vals = [h["domain_scores"].get(domain, 0) for h in history]
        fig.add_trace(go.Scatter(
            x=dates, y=domain_vals,
            mode="lines+markers",
            name=domain,
            line=dict(width=1, dash="dot"),
            opacity=0.6,
        ))

    fig.update_layout(
        title=title,
        yaxis=dict(range=[0, 100], title="Score (%)"),
        xaxis=dict(title="Date"),
        height=400,
        margin=dict(t=50, b=30),
    )
    return fig
