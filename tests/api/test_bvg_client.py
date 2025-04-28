import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import requests
from requests import Response

from app.api.bvg_client import BVGClient


def test_get_max_age_valid():
    with BVGClient() as bvg_client:
        assert bvg_client._get_max_age("public, max-age: 3600, toto") == 3600


def test_get_max_age_missing(caplog):
    with BVGClient() as bvg_client:
        assert bvg_client._get_max_age("public, no-store") is None
        assert caplog.record_tuples == []


def test_get_max_age_invalid_1(caplog):
    with BVGClient() as bvg_client:
        assert bvg_client._get_max_age("max-age: oopsie") is None
        assert caplog.record_tuples == [
            (
                'bvg_client',
                logging.WARNING,
                'Failed to parse cache control directive: max-age: oopsie'
            )
        ]


def test_get_max_age_invalid_2(caplog):
    with BVGClient() as bvg_client:
        assert bvg_client._get_max_age("max-age-invalid:3600") is None
        assert caplog.record_tuples == []


def test_get_max_age_empty(caplog):
    with BVGClient() as bvg_client:
        assert bvg_client._get_max_age("") is None
        assert caplog.record_tuples == []


def test_call_api_still_valid_cache(requests_mock, caplog):
    with BVGClient(retry_delay_seconds=0) as bvg_client:
        url: str = f"{bvg_client.base_url}/radar"
        requests_mock.get(url, status_code=304)

        response: Response = Response()
        response._content = b'{"data": "cached"}'
        response.status_code = 200

        bvg_client.cache = {
            url: {
                'etag': '35ebdc53-96a9-4ce3-963c-79e4435281d0',
                'response': response,
                'expiry': datetime(2100, 1, 1).timestamp()  # still valid
            }
        }

        assert bvg_client._call_api(url=url) == {'data': 'cached'}
        assert caplog.record_tuples == [
            (
                'bvg_client',
                logging.INFO,
                f'The cached response for {url} has not expired yet'
            )
        ]


def test_call_api_http_304_valid_cache(requests_mock, caplog):
    with BVGClient(retry_delay_seconds=0) as bvg_client:
        url: str = f"{bvg_client.base_url}/radar"
        requests_mock.get(url, status_code=304)

        response: Response = Response()
        response._content = b'{"data": "cached"}'
        response.status_code = 200

        bvg_client.cache = {
            url: {
                'etag': '35ebdc53-96a9-4ce3-963c-79e4435281d0',
                'response': response,
                'expiry': datetime(2000, 1, 1).timestamp()  # expired
            }
        }

        assert bvg_client._call_api(url=url) == {'data': 'cached'}
        assert caplog.record_tuples == [
            (
                'bvg_client',
                logging.INFO,
                f'Attempt 1/3 for {url}'
            ), (
                'bvg_client',
                logging.INFO,
                f'The cached response for {url} is still valid'
            )
        ]


def test_call_api_http_429_rate_limited(requests_mock, caplog):
    with BVGClient(retry_delay_seconds=0) as bvg_client:
        url: str = f"{bvg_client.base_url}/radar"
        requests_mock.get(url, status_code=429, text="Too many requests")
        assert bvg_client._call_api(url=url) is None
        assert caplog.record_tuples == [
            (
                'bvg_client',
                logging.INFO,
                f'Attempt 1/3 for {url}'
            ), (
                'bvg_client',
                logging.WARNING,
                'The rate limit has been reached '
            ), (
                'bvg_client',
                logging.INFO,
                f'Attempt 2/3 for {url}'
            ), (
                'bvg_client',
                logging.WARNING,
                'The rate limit has been reached '
            ), (
                'bvg_client',
                logging.INFO,
                f'Attempt 3/3 for {url}'
            ), (
                'bvg_client',
                logging.WARNING,
                'The rate limit has been reached '
            ), (
                'bvg_client',
                logging.ERROR,
                f'All attempts for {url} have failed'
            )
        ]


def test_call_api_http_200(requests_mock, caplog):
    with BVGClient(retry_delay_seconds=0) as bvg_client:
        url: str = f"{bvg_client.base_url}/radar"
        requests_mock.get(
            url,
            status_code=200,
            headers={
                'ETag': '35ebdc53-96a9-4ce3-963c-79e4435281d0',
                'Cache-Control': 'original, max-age: 3600, public',
            },
            content=b'{"data": "cached"}'
        )

        assert bvg_client._call_api(
            url=url,
            now=datetime(2000, 1, 1).timestamp()
        ) == {'data': 'cached'}

        cache: Dict[str, Dict[str, Any]] = bvg_client.cache
        del cache[url]['response']

        assert bvg_client.cache == {
            url: {
                'etag': '35ebdc53-96a9-4ce3-963c-79e4435281d0',
                'expiry': 946688400.0
            }
        }
        assert caplog.record_tuples == [
            (
                'bvg_client',
                logging.INFO,
                f'Attempt 1/3 for {url}'
            ), (
                'bvg_client',
                logging.INFO,
                f'The response for {url} is successful'
            ), (
                'bvg_client',
                logging.INFO,
                'An ETag is provided, caching the response'
            )
        ]


def test_call_api_http_404_not_found(requests_mock, caplog):
    with BVGClient() as bvg_client:
        url: str = f"{bvg_client.base_url}/bad-endpoint"
        requests_mock.get(url, status_code=404, text="Resource not found")
        assert bvg_client._call_api(url=url) is None
        assert caplog.record_tuples == [
            (
                'bvg_client',
                logging.INFO,
                f'Attempt 1/3 for {url}'
            ), (
                'bvg_client',
                logging.WARNING,
                f'The response for {url} is unsuccessful: HTTP code 404'
            ), (
                'bvg_client',
                logging.WARNING,
                f'The response for {url} is unsuccessful: Resource not found'
            )
        ]


def test_get_stops_all(requests_mock):
    with BVGClient() as bvg_client:
        with open("tests/api/response_samples/stops/all.json", "rb") as file:
            api_response_content: bytes = file.read()
            expected: List[Dict[str, Any]] = json.loads(str(api_response_content, "utf-8"))

        requests_mock.get(
            f"{bvg_client.base_url}/stops",
            content=api_response_content,
        )

        assert bvg_client.get_stops() == expected


def test_get_stops_query(requests_mock):
    with BVGClient() as bvg_client:
        with open("tests/api/response_samples/stops/query.json", "rb") as file:
            api_response_content: bytes = file.read()
            expected: List[Dict[str, Any]] = json.loads(str(api_response_content, "utf-8"))

        requests_mock.get(
            f"{bvg_client.base_url}/stops?results=1&query=Gleisdreieck&completion=True&fuzzy=True",
            content=api_response_content,
        )

        assert bvg_client.get_stops(query="Gleisdreieck", max_results=1) == expected


def test_get_stops_empty(requests_mock):
    with BVGClient() as bvg_client:
        with open("tests/api/response_samples/stops/empty.json", "rb") as file:
            api_response_content: bytes = file.read()
            expected: List[Dict[str, Any]] = json.loads(str(api_response_content, "utf-8"))

        requests_mock.get(
            f"{bvg_client.base_url}/stops?results=5&query=TrucMucheBahnof&completion=True&fuzzy=True",
            content=api_response_content,
        )

        assert bvg_client.get_stops(query="TrucMucheBahnof", max_results=5) == expected


def test_get_radar_all(requests_mock):
    with BVGClient() as bvg_client:
        with open("tests/api/response_samples/radar/all.json", "rb") as file:
            api_response_content: bytes = file.read()
            expected: Dict[str, Any] = json.loads(str(api_response_content, "utf-8"))

        requests_mock.get(
            f"{bvg_client.base_url}/radar?north=52.52411&west=13.41002&south=52.51942&east=13.41709&results=256&duration=30&frames=1&polylines=False&language=en&pretty=False",
            content=api_response_content,
        )

        assert bvg_client.get_radar(
            north_latitude=52.52411,
            west_longitude=13.41002,
            south_latitude=52.51942,
            east_longitude=13.41709,
        ) == expected


def test_get_radar_empty(requests_mock):
    with BVGClient() as bvg_client:
        with open("tests/api/response_samples/radar/empty.json", "rb") as file:
            api_response_content: bytes = file.read()
            expected: Dict[str, Any] = json.loads(str(api_response_content, "utf-8"))

        requests_mock.get(
            f"{bvg_client.base_url}/radar?north=52.52411&west=13.41002&south=52.51942&east=13.41709&results=256&duration=30&frames=1&polylines=False&language=en&pretty=False",
            content=api_response_content,
        )

        assert bvg_client.get_radar(
            north_latitude=52.52411,
            west_longitude=13.41002,
            south_latitude=52.51942,
            east_longitude=13.41709,
        ) == expected


def test_get_radar_bad_parameters(requests_mock):
    with BVGClient() as bvg_client:
        with open("tests/api/response_samples/radar/bad_parameters.json", "rb") as file:
            api_response_content: bytes = file.read()
            expected: Dict[str, Any] = json.loads(str(api_response_content, "utf-8"))

        requests_mock.get(
            f"{bvg_client.base_url}/radar?north=52.51&west=13.41&south=52.51&east=13.41&results=256&duration=30&frames=1&polylines=False&language=en&pretty=False",
            content=api_response_content,
        )

        assert bvg_client.get_radar(
            north_latitude=52.51,
            west_longitude=13.41,
            south_latitude=52.51,
            east_longitude=13.41,
        ) == expected
