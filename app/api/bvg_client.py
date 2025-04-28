import logging
import time
from logging import Logger
from typing import Any, Dict, List, Optional, Union

from requests import Response, Session

from config import Config


class BVGClient:
    """
    Client for the BVG API
    The API has no authentification but a rate limit of 100 requests per minute.
    The API sends ETag and Cache-Control headers to allow the client to cache responses.
    Cache format: ``{url: {"etag": str, "response": requests.Response, "expiry": float}}``
    """
    logger: Logger = logging.getLogger("bvg_client")
    base_url: str = "https://v6.bvg.transport.rest"

    def __init__(
            self,
            max_retries: int = Config.BVG_API_MAX_RETRIES,
            retry_delay_seconds: int = Config.BVG_API_RETRY_DELAY_SECONDS
    ):
        self.session: Session = Session()
        self.cache: Dict[str, Any] = {}
        self.max_retries: int = max_retries
        self.retry_delay_seconds: int = retry_delay_seconds
        self.logger.setLevel(Config.LOG_LEVEL)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _get_max_age(self, cache_control: str) -> Optional[int]:
        try:
            directives: List[str] = cache_control.split(",")

            for directive in directives:
                if directive.strip().startswith('max-age:'):
                    return int(directive.strip().split(':')[1].strip())
        except Exception:
            self.logger.warning(f"Failed to parse cache control directive: {cache_control}")

        return None


    def _call_api(
            self,
            url: str,
            params: Optional[Dict[str, Any]] = None,
            now: float = time.time()
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Call the API on the given URL and return the payload.
        If the request limit has been reached it retries after ``retry_delay_seconds`` seconds.
        The function attempts to recover a response from the cache if available.
        :param url:
        :param params:
        :return:
        """
        headers: Dict[str, Any] = {}
        cached = self.cache.get(url)

        if cached is not None:
            headers['If-None-Match'] = cached['etag']

            if cached['expiry'] and cached['expiry'] > now:
                self.logger.info(f"The cached response for {url} has not expired yet")
                response: Response = cached['response']
                return response.json()

        for attempt in range(1, self.max_retries + 1):
            self.logger.info(f"Attempt {attempt}/{self.max_retries} for {url}")
            response: Response = self.session.get(
                url=url,
                params=params,
                headers=headers,
            )

            if response.status_code == 304 and cached:
                self.logger.info(f"The cached response for {url} is still valid")
                return cached['response'].json()
            elif response.status_code == 429:
                self.logger.warning("The rate limit has been reached ")
                time.sleep(self.retry_delay_seconds)
                continue
            elif response.status_code == 200:
                self.logger.info(f"The response for {url} is successful")
                etag: Optional[str] = response.headers.get('ETag')
                cache_control: str = response.headers.get('Cache-Control', '')
                max_age = self._get_max_age(cache_control)

                if etag is not None:
                    self.logger.info(f"An ETag is provided, caching the response")
                    self.cache[url] = {
                        'etag': etag,
                        'response': response,
                        'expiry': now + max_age if max_age is not None else None
                    }

                return response.json()

            else:
                self.logger.warning(f"The response for {url} is unsuccessful: HTTP code {response.status_code}")
                self.logger.warning(f"The response for {url} is unsuccessful: {response.text}")
                return None

        self.logger.error(f"All attempts for {url} have failed")
        return None

    def get_stops(
            self,
            query: Optional[str] = None,
            fuzzy: bool = True,
            max_results: int = 10_000
    ) -> List[Dict[str, Any]]:
        """
        Return matching stops or all stops if no query is given.
        :param query: A stop name or part of a stop name, or None to return all stops
        :param fuzzy: Allow not perfect matches
        :param max_results: Maximum number of returned results (API default is 5)
        :return: The API JSON response or None if an error occurred
        """
        url: str = f"{self.base_url}/stops"
        params: Dict[str, Any] = {
            "results": max_results
        }

        if query is not None:
            params['query'] = query
            params['completion'] = True
            params['fuzzy'] = fuzzy

        response: List[Dict[str, Any]] = self._call_api(
            url=url,
            params=params
        )

        return response

    def get_radar(
            self,
            north_latitude: float,
            west_longitude: float,
            south_latitude: float,
            east_longitude: float,
            max_number_of_vehicles: int = 256,
            seconds_between_frames: int = 30,
            frames: int = 1,
            polylines: bool = False,
            language: str = 'en',
            pretty_print_json: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Find all vehicles currently in an area as well as their movements
        :param north_latitude: **Required** Northern latitude
        :param west_longitude: **Required** Western longitude
        :param south_latitude: **Required** Southern latitude
        :param east_longitude: **Required** Eastern longitude
        :param max_number_of_vehicles: Max. number of vehicles (default 256)
        :param seconds_between_frames: Compute frames for the next n seconds (default 30)
        :param frames: Number of frames to compute (default 3)
        :param polylines: Fetch & parse a geographic shape for the movement of each vehicle?
        :param language: Language of the results.
        :param pretty_print_json: Pretty-print JSON responses?
        :return: The API JSON response or None if an error occurred
        """
        url: str = f"{self.base_url}/radar"
        params: Dict[str, Any] = {
            "north": north_latitude,
            "west": west_longitude,
            "south": south_latitude,
            "east": east_longitude,
            "results": max_number_of_vehicles,
            "duration": seconds_between_frames,
            "frames": frames,
            "polylines": polylines,
            "language": language,
            "pretty": pretty_print_json
        }

        return self._call_api(
            url=url,
            params=params
        )
