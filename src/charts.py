"""Chart generation for price dashboards."""

import logging
from datetime import date, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from .models import Product

logger = logging.getLogger(__name__)

# Chart styling
plt.style.use("seaborn-v0_8-whitegrid")
COLORS = {
    "range": "#e1f5fe",  # Light blue for min-max range
    "median": "#1976d2",  # Blue for median
    "mean": "#ff9800",  # Orange for mean
    "text": "#333333",
}


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """Load and parse CSV data."""
    if not csv_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date")
    return df


def create_dashboard(product: Product, csv_path: Path, output_path: Path) -> bool:
    """Create a dashboard PNG with multiple timeframes."""
    df = load_csv_data(csv_path)

    if df.empty:
        logger.warning(f"No data for {product.name}, skipping chart")
        return False

    today = date.today()

    # Filter data for different timeframes
    df_week = df[df["date"] >= pd.Timestamp(today - timedelta(days=7))]
    df_month = df[df["date"] >= pd.Timestamp(today - timedelta(days=30))]
    df_all = df  # All historical data

    # Create figure with subplots
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), height_ratios=[1, 1, 1.2])
    # Skip emoji in chart title (font support issues), only use in README
    fig.suptitle(f"{product.name} - Price Dashboard", fontsize=16, fontweight="bold")

    # Plot each timeframe
    _plot_timeframe(axes[0], df_week, "Last 7 Days", show_points=True)
    _plot_timeframe(axes[1], df_month, "Last 30 Days", show_points=len(df_month) <= 30)
    _plot_timeframe(axes[2], df_all, "All Time", show_points=False)

    # Add stats box
    if not df.empty:
        latest = df.iloc[-1]
        stats_text = (
            f"Latest: {latest['date'].strftime('%Y-%m-%d')} | "
            f"Count: {int(latest['count'])} | "
            f"Min: {int(latest['min']):,} RON | "
            f"Max: {int(latest['max']):,} RON | "
            f"Median: {int(latest['median']):,} RON"
        )
        fig.text(0.5, 0.02, stats_text, ha="center", fontsize=10, color=COLORS["text"])

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info(f"Dashboard saved to {output_path}")
    return True


def _plot_timeframe(ax: plt.Axes, df: pd.DataFrame, title: str, show_points: bool = False) -> None:
    """Plot a single timeframe chart."""
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left")

    if df.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, color="gray")
        ax.set_xticks([])
        ax.set_yticks([])
        return

    dates = df["date"]

    # Fill between min and max (price range)
    ax.fill_between(dates, df["min"], df["max"], alpha=0.3, color=COLORS["range"], label="Min-Max Range")

    # Plot median line
    ax.plot(dates, df["median"], color=COLORS["median"], linewidth=2, label="Median", marker="o" if show_points else None, markersize=4)

    # Plot mean line (dashed)
    ax.plot(dates, df["mean"], color=COLORS["mean"], linewidth=1.5, linestyle="--", label="Mean", alpha=0.8)

    # Formatting
    ax.set_ylabel("Price (RON)")
    ax.legend(loc="upper right", fontsize=8)

    # X-axis date formatting
    if len(df) <= 7:
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    elif len(df) <= 31:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Y-axis formatting
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))

    # Grid
    ax.grid(True, alpha=0.3)


def create_overview(products: list[Product], data_dir: Path, output_path: Path) -> bool:
    """Create an overview chart showing all products."""
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle("OLX Price Index - Overview", fontsize=16, fontweight="bold")

    has_data = False
    for product in products:
        csv_path = data_dir / f"{product.slug}.csv"
        df = load_csv_data(csv_path)

        if df.empty:
            continue

        has_data = True
        label = product.name
        ax.plot(df["date"], df["median"], linewidth=2, label=label, marker="o", markersize=3)

    if not has_data:
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center", transform=ax.transAxes, color="gray", fontsize=14)

    ax.set_ylabel("Median Price (RON)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))

    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info(f"Overview saved to {output_path}")
    return True
