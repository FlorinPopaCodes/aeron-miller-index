import httpx
import pytest

from src.scraper import MAX_RETRIES, OLXScraper, ScraperError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip real backoff delays so retry tests run instantly."""
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda seconds: None)


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


SUCCESS_BODY = {
    "data": {
        "clientCompatibleListings": {
            "__typename": "ListingSuccess",
            "data": [],
            "metadata": {"total_elements": 0},
        }
    }
}


def test_make_request_retries_on_429_and_respects_retry_after() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json=SUCCESS_BODY)

    with OLXScraper() as scraper:
        scraper.client = httpx.Client(transport=httpx.MockTransport(handler))
        data = scraper._make_request("test", offset=0)

    assert calls["n"] == 3
    assert data == SUCCESS_BODY


def test_make_request_gives_up_after_max_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={})

    with OLXScraper() as scraper:
        scraper.client = httpx.Client(transport=httpx.MockTransport(handler))
        with pytest.raises(httpx.HTTPStatusError):
            scraper._make_request("test", offset=0)

    assert calls["n"] == MAX_RETRIES


def test_make_request_does_not_retry_on_graphql_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"errors": [{"message": "bad query"}]})

    with OLXScraper() as scraper:
        scraper.client = httpx.Client(transport=httpx.MockTransport(handler))
        with pytest.raises(ScraperError):
            scraper._make_request("test", offset=0)

    assert calls["n"] == 1
