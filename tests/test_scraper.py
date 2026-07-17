import pytest

from src.scraper import OLXScraper, ScraperError


def test_parse_listings_success() -> None:
    data = {
        "data": {
            "clientCompatibleListings": {
                "__typename": "ListingSuccess",
                "data": [
                    {
                        "id": "1",
                        "title": "Item 1",
                        "params": [
                            {
                                "key": "price",
                                "value": {
                                    "__typename": "PriceParam",
                                    "value": 100,
                                    "currency": "RON",
                                },
                            }
                        ],
                        "location": {
                            "city": {"name": "Bucharest"},
                            "region": {"name": "Ilfov"},
                        },
                    },
                    {
                        "id": "2",
                        "title": "Item 2",
                        "params": [
                            {
                                "key": "price",
                                "value": {
                                    "__typename": "PriceParam",
                                    "value": 200,
                                    "currency": "RON",
                                },
                            }
                        ],
                        "location": {},
                    },
                    {
                        "id": "3",
                        "title": "Item 3",
                        "params": [{"key": "not_price", "value": {}}],
                        "location": {},
                    },
                ],
                "metadata": {"total_elements": 2},
            }
        }
    }

    with OLXScraper() as scraper:
        listings = list(scraper._parse_listings(data))

    assert len(listings) == 2
    assert listings[0].price == 100
    assert listings[0].city == "Bucharest"
    assert listings[1].price == 200


def test_parse_listings_error() -> None:
    data = {
        "data": {
            "clientCompatibleListings": {
                "__typename": "ListingError",
                "error": {"code": "ERR", "detail": "Bad query"},
            }
        }
    }

    with OLXScraper() as scraper:
        with pytest.raises(ScraperError):
            list(scraper._parse_listings(data))


def test_parse_listings_missing_result() -> None:
    data = {"data": {}}

    with OLXScraper() as scraper:
        with pytest.raises(ScraperError):
            list(scraper._parse_listings(data))
