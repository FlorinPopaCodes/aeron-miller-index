"""Chart generation using Plotly."""

import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .models import Product

logger = logging.getLogger(__name__)

# Google-inspired color palette
COLORS = {
    "median": "#1a73e8",
    "mean": "#ea4335",
    "min": "#34a853",
    "max": "#fbbc04",
    "range": "rgba(66, 133, 244, 0.15)",
    "grid": "#e8e8e8",
}


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """Load and parse CSV data."""
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, parse_dates=["date"])
    return df.sort_values("date")


def create_dashboard(product: Product, csv_path: Path, output_path: Path) -> bool:
    """Create a single-chart dashboard showing price trends over time."""
    df = load_csv_data(csv_path)

    if df.empty:
        logger.warning(f"No data for {product.name}, skipping chart")
        return False

    fig = go.Figure()
    dates = df["date"]

    # Min-Max range fill (only if we have multiple points)
    if len(df) > 1:
        fig.add_trace(go.Scatter(
            x=pd.concat([dates, dates[::-1]]),
            y=pd.concat([df["max"], df["min"][::-1]]),
            fill="toself",
            fillcolor=COLORS["range"],
            line=dict(width=0),
            name="Min-Max Range",
            hoverinfo="skip",
        ))

    # Individual metric lines
    metrics = [
        ("min", "Min", COLORS["min"], "dot", 1),
        ("max", "Max", COLORS["max"], "dot", 1),
        ("mean", "Mean", COLORS["mean"], "dash", 2),
        ("median", "Median", COLORS["median"], "solid", 3),
    ]

    for col, name, color, dash, width in metrics:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df[col],
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=width, dash=dash),
            marker=dict(size=6 if col == "median" else 4),
            hovertemplate=f"{name}: %{{y:,.0f}} RON<extra></extra>",
        ))

    # Build subtitle with latest stats
    latest = df.iloc[-1]
    subtitle = (
        f"Latest: {latest['date'].strftime('%Y-%m-%d')} · "
        f"{int(latest['count'])} listings · "
        f"Median: {int(latest['median']):,} RON"
    )

    fig.update_layout(
        title=dict(
            text=f"<b>{product.name}</b><br><span style='font-size:12px;color:#666'>{subtitle}</span>",
            x=0.5,
            font=dict(size=18),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        xaxis=dict(showgrid=True, gridcolor=COLORS["grid"], tickformat="%d %b %Y"),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], title="Price (RON)", tickformat=","),
        height=500,
        width=1000,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(t=100, b=60, l=80, r=40),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(output_path), scale=2)
    logger.info(f"Dashboard saved to {output_path}")
    return True


def create_overview(products: list[Product], data_dir: Path, output_path: Path) -> bool:
    """Create an overview chart showing median prices for all products."""
    fig = go.Figure()
    colors = ["#1a73e8", "#ea4335", "#34a853", "#fbbc04", "#9c27b0", "#00bcd4"]
    has_data = False

    for i, product in enumerate(products):
        df = load_csv_data(data_dir / f"{product.slug}.csv")
        if df.empty:
            continue

        has_data = True
        label = f"{product.emoji} {product.name}" if product.emoji else product.name

        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["median"],
            mode="lines+markers",
            name=label,
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=8),
            hovertemplate=f"{product.name}<br>Median: %{{y:,.0f}} RON<extra></extra>",
        ))

    if not has_data:
        fig.add_annotation(
            text="No data yet",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="#999"),
        )

    fig.update_layout(
        title=dict(text="<b>OLX Price Index - Overview</b>", x=0.5, font=dict(size=18)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        xaxis=dict(showgrid=True, gridcolor=COLORS["grid"], tickformat="%d %b %Y"),
        yaxis=dict(showgrid=True, gridcolor=COLORS["grid"], title="Median Price (RON)", tickformat=","),
        height=450,
        width=1000,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(t=80, b=60, l=80, r=40),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(output_path), scale=2)
    logger.info(f"Overview saved to {output_path}")
    return True
