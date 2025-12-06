"""OLX GraphQL scraper with retry logic."""

import logging
import time
from typing import Iterator

import httpx

from .models import Listing, Product

logger = logging.getLogger(__name__)

OLX_GRAPHQL_URL = "https://www.olx.ro/apigateway/graphql"

# Simplified GraphQL query - only fields we need
GRAPHQL_QUERY = """
query ListingSearchQuery($searchParameters: [SearchParameter!]) {
  clientCompatibleListings(searchParameters: $searchParameters) {
    __typename
    ... on ListingSuccess {
      data {
        id
        title
        params {
          key
          value {
            __typename
            ... on PriceParam {
              value
              currency
            }
          }
        }
        location {
          city { name }
          region { name }
        }
      }
      metadata {
        total_elements
      }
    }
    ... on ListingError {
      error { code detail }
    }
  }
}
"""

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, exponential backoff
REQUEST_DELAY = 0.5  # delay between paginated requests
ITEMS_PER_PAGE = 50


class OLXScraper:
    """Scraper for OLX GraphQL API."""

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
        )

    def __enter__(self) -> "OLXScraper":
        return self

    def __exit__(self, *args) -> None:
        self.client.close()

    def _make_request(self, query: str, offset: int = 0) -> dict:
        """Make a GraphQL request with retry logic."""
        variables = {
            "searchParameters": [
                {"key": "offset", "value": str(offset)},
                {"key": "limit", "value": str(ITEMS_PER_PAGE)},
                {"key": "query", "value": query},
            ]
        }

        payload = {"query": GRAPHQL_QUERY, "variables": variables}

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.post(OLX_GRAPHQL_URL, json=payload)

                if response.status_code == 429:
                    wait_time = 60
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_BASE ** (attempt + 1)
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_BASE ** (attempt + 1)
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

        return {}

    def _parse_listings(self, data: dict) -> Iterator[Listing]:
        """Parse GraphQL response into Listing objects."""
        result = data.get("data", {}).get("clientCompatibleListings", {})

        if result.get("__typename") == "ListingError":
            error = result.get("error", {})
            logger.error(f"OLX API error: {error.get('code')} - {error.get('detail')}")
            return

        listings = result.get("data", [])
        for item in listings:
            price = self._extract_price(item)
            if price is None:
                continue

            location = item.get("location", {})
            city = location.get("city", {}).get("name", "")
            region = location.get("region", {}).get("name", "")

            yield Listing(
                id=item.get("id", ""),
                title=item.get("title", ""),
                price=price,
                city=city,
                region=region,
            )

    def _extract_price(self, item: dict) -> int | None:
        """Extract price from listing params."""
        params = item.get("params", [])
        for param in params:
            if param.get("key") == "price":
                value = param.get("value", {})
                if value.get("__typename") == "PriceParam":
                    price_val = value.get("value")
                    if price_val is not None:
                        return int(price_val)
        return None

    def _get_total_count(self, data: dict) -> int:
        """Get total number of listings from response."""
        result = data.get("data", {}).get("clientCompatibleListings", {})
        return result.get("metadata", {}).get("total_elements", 0)

    def fetch_all(self, product: Product) -> list[Listing]:
        """Fetch all listings for a product with pagination."""
        logger.info(f"Fetching listings for: {product.name}")

        # First request to get total count
        data = self._make_request(product.query, offset=0)
        total = self._get_total_count(data)
        logger.info(f"Total listings found: {total}")

        if total == 0:
            return []

        # Collect first page
        listings = list(self._parse_listings(data))

        # Fetch remaining pages
        offset = ITEMS_PER_PAGE
        while offset < total:
            time.sleep(REQUEST_DELAY)  # Rate limiting
            data = self._make_request(product.query, offset=offset)
            listings.extend(self._parse_listings(data))
            offset += ITEMS_PER_PAGE
            logger.debug(f"Fetched {len(listings)}/{total} listings")

        logger.info(f"Collected {len(listings)} listings with valid prices")
        return listings
