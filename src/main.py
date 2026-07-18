"""Main orchestration for Aeron Miller Index."""

import logging
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from .charts import create_dashboard, create_overview, load_csv_data
from .models import DailyStats, Product
from .scraper import OLXScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_ROOT_DIR = Path(__file__).parent.parent


@dataclass(frozen=True)
class Paths:
    root: Path
    data_dir: Path
    images_dir: Path
    products_file: Path
    readme_file: Path


def find_repo_root(start: Path, marker: str = "products.yaml") -> Path | None:
    """Find the repo root by walking up from a starting directory."""
    for parent in [start, *start.parents]:
        if (parent / marker).is_file():
            return parent
    return None


def resolve_root() -> Path:
    """Resolve the repository root with env override and cwd discovery."""
    env_root = os.environ.get("AMI_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    discovered = find_repo_root(Path.cwd())
    if discovered:
        return discovered

    return DEFAULT_ROOT_DIR


def resolve_paths() -> Paths:
    """Resolve all working paths for config, outputs, and README."""
    env_products = os.environ.get("AMI_PRODUCTS_FILE")
    if env_products:
        products_file = Path(env_products).expanduser().resolve()
        if not products_file.is_file():
            raise FileNotFoundError(
                f"AMI_PRODUCTS_FILE does not point to a file: {products_file}"
            )
        root = products_file.parent
    else:
        root = resolve_root()
        products_file = root / "products.yaml"

    if not products_file.is_file():
        raise FileNotFoundError(
            "Could not locate products.yaml. "
            "Run from the repo root or set AMI_ROOT/AMI_PRODUCTS_FILE."
        )

    return Paths(
        root=root,
        data_dir=root / "data",
        images_dir=root / "images",
        products_file=products_file,
        readme_file=root / "README.md",
    )


def load_products(products_file: Path) -> list[Product]:
    """Load products from YAML config."""
    with open(products_file, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

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

    row = pd.DataFrame([{
        "date": stats.date,
        "count": stats.count,
        "min": stats.min_price,
        "max": stats.max_price,
        "mean": stats.mean_price,
        "median": stats.median_price,
    }])

    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    row.to_csv(csv_path, mode="a", header=write_header, index=False)

    logger.info(f"Appended stats to {csv_path}")


def should_update_today(csv_path: Path) -> bool:
    """Check if we already have data for today."""
    df = load_csv_data(csv_path)
    if df.empty:
        return True

    today = date.today()
    if (df["date"].dt.date == today).any():
        logger.info(f"Data for {today.isoformat()} already exists in {csv_path}")
        return False

    return True


def generate_readme(
    products: list[Product],
    data_dir: Path,
    readme_file: Path,
    base_url: str,
) -> None:
    """Generate README.md with current stats."""
    # Cache-busting: use today's date as version
    cache_bust = date.today().strftime("%Y%m%d")

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
        csv_path = data_dir / f"{product.slug}.csv"
        img_url = f"{base_url}/images/{product.slug}_dashboard.png?v={cache_bust}"

        lines.append(f"## {product.emoji} {product.name}")
        lines.append("")
        lines.append(f"![{product.name} Dashboard]({img_url})")
        lines.append("")

        df = load_csv_data(csv_path)
        if not df.empty:
            latest = df.iloc[-1]
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Listings | {int(latest['count'])} |")
            lines.append(f"| Min | {int(latest['min']):,} RON |")
            lines.append(f"| Max | {int(latest['max']):,} RON |")
            lines.append(f"| Median | {int(latest['median']):,} RON |")
            lines.append(f"| Average | {int(latest['mean']):,} RON |")
            lines.append(f"| Last Update | {latest['date'].strftime('%Y-%m-%d')} |")
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

    with open(readme_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Generated {readme_file}")


def main() -> None:
    """Main entry point."""
    logger.info("Starting Aeron Miller Index update")

    try:
        paths = resolve_paths()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    logger.info(f"Using repository root: {paths.root}")

    products = load_products(paths.products_file)

    if not products:
        logger.warning("No products configured, exiting")
        return

    failed_products = []

    with OLXScraper() as scraper:
        for product in products:
            product_failed = False
            csv_path = paths.data_dir / f"{product.slug}.csv"
            dashboard_path = paths.images_dir / f"{product.slug}_dashboard.png"

            try:
                logger.info(f"Processing: {product.name}")

                # Check if we already have today's data
                if should_update_today(csv_path):
                    # Fetch listings
                    listings = scraper.fetch_all(product)

                    if not listings:
                        logger.warning(f"No listings found for {product.name}")
                    else:
                        # Calculate stats
                        prices = [listing.price for listing in listings]
                        stats = DailyStats.from_prices(date.today(), prices)
                        logger.info(
                            f"Stats: count={stats.count}, min={stats.min_price}, max={stats.max_price}, median={stats.median_price}"
                        )

                        # Save to CSV
                        append_to_csv(csv_path, stats)
                else:
                    logger.info(f"Skipping {product.name} - already updated today")

            except Exception as e:
                logger.error(f"Failed to update {product.name}: {e}", exc_info=True)
                product_failed = True

            try:
                if csv_path.exists():
                    create_dashboard(product, csv_path, dashboard_path)
            except Exception as e:
                logger.error(
                    f"Failed to generate dashboard for {product.name}: {e}",
                    exc_info=True,
                )
                product_failed = True

            if product_failed:
                failed_products.append(product.name)

    # Generate overview chart
    overview_path = paths.images_dir / "overview.png"
    create_overview(products, paths.data_dir, overview_path)

    # Update README
    base_url = os.environ.get(
        "AMI_BASE_URL",
        "https://raw.githubusercontent.com/FlorinPopaCodes/aeron-miller-index/main",
    )
    generate_readme(products, paths.data_dir, paths.readme_file, base_url)

    # Exit with error if any products failed
    if failed_products:
        logger.error(
            f"Failed to process {len(failed_products)} product(s): {', '.join(failed_products)}"
        )
        sys.exit(1)

    logger.info("Update complete!")


if __name__ == "__main__":
    main()
