"""Chart generation using Plotly."""

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .models import Product

logger = logging.getLogger(__name__)

# Color scheme
COLORS = {
    "range": "rgba(66, 133, 244, 0.2)",  # Light blue fill
    "range_line": "rgba(66, 133, 244, 0.4)",
    "median": "#1a73e8",  # Google blue
    "mean": "#ea4335",  # Google red
    "min": "#34a853",  # Google green
    "max": "#fbbc04",  # Google yellow
    "grid": "#e0e0e0",
    "bg": "#ffffff",
}


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """Load and parse CSV data."""
    if not csv_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date")
    return df


def create_dashboard(product: Product, csv_path: Path, output_path: Path) -> bool:
    """Create a dashboard PNG with multiple timeframes using Plotly."""
    df = load_csv_data(csv_path)

    if df.empty:
        logger.warning(f"No data for {product.name}, skipping chart")
        return False

    today = date.today()

    # Filter data for different timeframes
    df_week = df[df["date"] >= pd.Timestamp(today - timedelta(days=7))]
    df_month = df[df["date"] >= pd.Timestamp(today - timedelta(days=30))]
    df_all = df

    # Create subplots
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=("Last 7 Days", "Last 30 Days", "All Time"),
        vertical_spacing=0.08,
        row_heights=[0.33, 0.33, 0.34],
    )

    # Add traces for each timeframe
    _add_price_traces(fig, df_week, row=1)
    _add_price_traces(fig, df_month, row=2)
    _add_price_traces(fig, df_all, row=3)

    # Layout
    latest = df.iloc[-1]
    fig.update_layout(
        title=dict(
            text=f"{product.name} - Price Dashboard",
            font=dict(size=20, color="#333"),
            x=0.5,
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        height=900,
        width=1200,
        plot_bgcolor=COLORS["bg"],
        paper_bgcolor=COLORS["bg"],
        font=dict(family="Arial, sans-serif", size=12, color="#333"),
        annotations=[
            dict(
                text=(
                    f"Latest: {latest['date'].strftime('%Y-%m-%d')} | "
                    f"Count: {int(latest['count'])} | "
                    f"Min: {int(latest['min']):,} RON | "
                    f"Max: {int(latest['max']):,} RON | "
                    f"Median: {int(latest['median']):,} RON | "
                    f"Mean: {int(latest['mean']):,} RON"
                ),
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.02,
                showarrow=False,
                font=dict(size=11, color="#666"),
            )
        ],
    )

    # Update axes
    for i in range(1, 4):
        fig.update_xaxes(
            showgrid=True,
            gridcolor=COLORS["grid"],
            tickformat="%d %b %Y" if i == 3 else "%d %b",
            row=i,
            col=1,
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor=COLORS["grid"],
            title_text="Price (RON)",
            tickformat=",",
            row=i,
            col=1,
        )

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(output_path), scale=2)

    logger.info(f"Dashboard saved to {output_path}")
    return True


def _add_price_traces(fig: go.Figure, df: pd.DataFrame, row: int) -> None:
    """Add price traces (range fill, min, max, median, mean) to a subplot."""
    if df.empty:
        return

    dates = df["date"]
    show_legend = row == 1  # Only show legend for first subplot

    # Min-Max range as filled area
    fig.add_trace(
        go.Scatter(
            x=pd.concat([dates, dates[::-1]]),
            y=pd.concat([df["max"], df["min"][::-1]]),
            fill="toself",
            fillcolor=COLORS["range"],
            line=dict(color=COLORS["range_line"], width=0),
            name="Min-Max Range",
            showlegend=show_legend,
            hoverinfo="skip",
        ),
        row=row,
        col=1,
    )

    # Min line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=df["min"],
            mode="lines+markers",
            name="Min",
            line=dict(color=COLORS["min"], width=1, dash="dot"),
            marker=dict(size=4),
            showlegend=show_legend,
            hovertemplate="Min: %{y:,.0f} RON<extra></extra>",
        ),
        row=row,
        col=1,
    )

    # Max line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=df["max"],
            mode="lines+markers",
            name="Max",
            line=dict(color=COLORS["max"], width=1, dash="dot"),
            marker=dict(size=4),
            showlegend=show_legend,
            hovertemplate="Max: %{y:,.0f} RON<extra></extra>",
        ),
        row=row,
        col=1,
    )

    # Median line (primary)
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=df["median"],
            mode="lines+markers",
            name="Median",
            line=dict(color=COLORS["median"], width=3),
            marker=dict(size=8, symbol="circle"),
            showlegend=show_legend,
            hovertemplate="Median: %{y:,.0f} RON<extra></extra>",
        ),
        row=row,
        col=1,
    )

    # Mean line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=df["mean"],
            mode="lines+markers",
            name="Mean",
            line=dict(color=COLORS["mean"], width=2, dash="dash"),
            marker=dict(size=6, symbol="square"),
            showlegend=show_legend,
            hovertemplate="Mean: %{y:,.0f} RON<extra></extra>",
        ),
        row=row,
        col=1,
    )


def create_overview(products: list[Product], data_dir: Path, output_path: Path) -> bool:
    """Create an overview chart showing median prices for all products."""
    fig = go.Figure()

    colors = ["#1a73e8", "#ea4335", "#34a853", "#fbbc04", "#9c27b0", "#00bcd4"]
    has_data = False

    for i, product in enumerate(products):
        csv_path = data_dir / f"{product.slug}.csv"
        df = load_csv_data(csv_path)

        if df.empty:
            continue

        has_data = True
        color = colors[i % len(colors)]

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["median"],
                mode="lines+markers",
                name=f"{product.emoji} {product.name}" if product.emoji else product.name,
                line=dict(color=color, width=2),
                marker=dict(size=8),
                hovertemplate=f"{product.name}<br>Median: %{{y:,.0f}} RON<br>%{{x}}<extra></extra>",
            )
        )

    if not has_data:
        fig.add_annotation(
            text="No data yet",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20, color="#999"),
        )

    fig.update_layout(
        title=dict(
            text="OLX Price Index - Overview",
            font=dict(size=20, color="#333"),
            x=0.5,
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor=COLORS["grid"],
            tickformat="%d %b %Y",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["grid"],
            title="Median Price (RON)",
            tickformat=",",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        height=500,
        width=1200,
        plot_bgcolor=COLORS["bg"],
        paper_bgcolor=COLORS["bg"],
        font=dict(family="Arial, sans-serif", size=12, color="#333"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(output_path), scale=2)

    logger.info(f"Overview saved to {output_path}")
    return True
