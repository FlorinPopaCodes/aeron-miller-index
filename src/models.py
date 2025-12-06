"""Data models for Aeron Miller Index."""

from dataclasses import dataclass, field
from datetime import date
from statistics import mean, median


@dataclass
class Product:
    """Product configuration from products.yaml."""

    slug: str
    name: str
    query: str
    emoji: str = ""


@dataclass
class Listing:
    """A single OLX listing."""

    id: str
    title: str
    price: int  # in RON
    currency: str = "RON"
    city: str = ""
    region: str = ""


@dataclass
class DailyStats:
    """Aggregated statistics for a single day."""

    date: date
    count: int
    min_price: int
    max_price: int
    mean_price: float
    median_price: float

    @classmethod
    def from_prices(cls, day: date, prices: list[int]) -> "DailyStats":
        """Create DailyStats from a list of prices."""
        if not prices:
            raise ValueError("Cannot create stats from empty price list")

        return cls(
            date=day,
            count=len(prices),
            min_price=min(prices),
            max_price=max(prices),
            mean_price=round(mean(prices), 2),
            median_price=round(median(prices), 2),
        )

    def to_csv_row(self) -> str:
        """Convert to CSV row string."""
        return f"{self.date},{self.count},{self.min_price},{self.max_price},{self.mean_price},{self.median_price}"

    @classmethod
    def csv_header(cls) -> str:
        """Return CSV header."""
        return "date,count,min,max,mean,median"
