"""Main orchestration for Aeron Miller Index."""

import logging
from datetime import date
from pathlib import Path

import yaml

from .charts import create_dashboard, create_overview
from .models import DailyStats, Product
from .scraper import OLXScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
IMAGES_DIR = ROOT_DIR / "images"
PRODUCTS_FILE = ROOT_DIR / "products.yaml"
README_FILE = ROOT_DIR / "README.md"


def load_products() -> list[Product]:
    """Load products from YAML config."""
    with open(PRODUCTS_FILE) as f:
        config = yaml.safe_load(f)

    products = []
    for item in config.get("products", []):
        products.append(
            Product(
                slug=item["slug"],
                name=item["name"],
                query=item["query"],
                emoji=item.get("emoji", ""),
            )
        )

    logger.info(f"Loaded {len(products)} products from config")
    return products


def append_to_csv(csv_path: Path, stats: DailyStats) -> None:
    """Append daily stats to CSV file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file exists and has content
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with open(csv_path, "a") as f:
        if write_header:
            f.write(DailyStats.csv_header() + "\n")
        f.write(stats.to_csv_row() + "\n")

    logger.info(f"Appended stats to {csv_path}")


def should_update_today(csv_path: Path) -> bool:
    """Check if we already have data for today."""
    if not csv_path.exists():
        return True

    today_str = date.today().isoformat()

    with open(csv_path) as f:
        for line in f:
            if line.startswith(today_str):
                logger.info(f"Data for {today_str} already exists in {csv_path}")
                return False

    return True


def generate_readme(products: list[Product]) -> None:
    """Generate README.md with current stats."""
    # Cache-busting: use today's date as version
    cache_bust = date.today().strftime("%Y%m%d")
    base_url = "https://raw.githubusercontent.com/FlorinPopaCodes/aeron-miller-index/main"

    lines = [
        "# OLX Price Index",
        "",
        "Daily price tracking for products on OLX.ro as a proxy for economic indicators.",
        "",
        f"![Overview]({base_url}/images/overview.png?v={cache_bust})",
        "",
        "---",
        "",
    ]

    for product in products:
        csv_path = DATA_DIR / f"{product.slug}.csv"
        img_url = f"{base_url}/images/{product.slug}_dashboard.png?v={cache_bust}"

        lines.append(f"## {product.emoji} {product.name}")
        lines.append("")
        lines.append(f"![{product.name} Dashboard]({img_url})")
        lines.append("")

        if csv_path.exists():
            # Read last line for latest stats
            with open(csv_path) as f:
                all_lines = f.readlines()
                if len(all_lines) > 1:  # Has data beyond header
                    last_line = all_lines[-1].strip()
                    parts = last_line.split(",")
                    if len(parts) == 6:
                        date_str, count, min_p, max_p, mean_p, median_p = parts
                        lines.append("| Metric | Value |")
                        lines.append("|--------|-------|")
                        lines.append(f"| Listings | {count} |")
                        lines.append(f"| Min | {int(float(min_p)):,} RON |")
                        lines.append(f"| Max | {int(float(max_p)):,} RON |")
                        lines.append(f"| Median | {int(float(median_p)):,} RON |")
                        lines.append(f"| Average | {int(float(mean_p)):,} RON |")
                        lines.append(f"| Last Update | {date_str} |")
                        lines.append("")

        lines.append("---")
        lines.append("")

    lines.extend(
        [
            "## About",
            "",
            "This index tracks prices of various products on OLX.ro to provide insights into market trends.",
            "",
            "**Metrics:**",
            "- **Count**: Number of active listings",
            "- **Min/Max**: Price range",
            "- **Median**: Middle price (robust to outliers)",
            "- **Average**: Mean price",
            "",
            "Data is collected daily via GitHub Actions.",
            "",
            "---",
            "",
            "*Generated automatically by [Aeron Miller Index](https://github.com/FlorinPopaCodes/aeron-miller-index)*",
        ]
    )

    with open(README_FILE, "w") as f:
        f.write("\n".join(lines))

    logger.info(f"Generated {README_FILE}")


def main() -> None:
    """Main entry point."""
    logger.info("Starting Aeron Miller Index update")

    products = load_products()

    if not products:
        logger.warning("No products configured, exiting")
        return

    with OLXScraper() as scraper:
        for product in products:
            logger.info(f"Processing: {product.name}")

            csv_path = DATA_DIR / f"{product.slug}.csv"

            # Check if we already have today's data
            if not should_update_today(csv_path):
                logger.info(f"Skipping {product.name} - already updated today")
                continue

            # Fetch listings
            listings = scraper.fetch_all(product)

            if not listings:
                logger.warning(f"No listings found for {product.name}")
                continue

            # Calculate stats
            prices = [listing.price for listing in listings]
            stats = DailyStats.from_prices(date.today(), prices)
            logger.info(
                f"Stats: count={stats.count}, min={stats.min_price}, max={stats.max_price}, median={stats.median_price}"
            )

            # Save to CSV
            append_to_csv(csv_path, stats)

            # Generate dashboard
            dashboard_path = IMAGES_DIR / f"{product.slug}_dashboard.png"
            create_dashboard(product, csv_path, dashboard_path)

    # Generate overview chart
    overview_path = IMAGES_DIR / "overview.png"
    create_overview(products, DATA_DIR, overview_path)

    # Update README
    generate_readme(products)

    logger.info("Update complete!")


if __name__ == "__main__":
    main()
