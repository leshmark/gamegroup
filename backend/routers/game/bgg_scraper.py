"""BoardGameGeek scraper for extracting game cover images."""

import os
import time
from curl_cffi import requests
import re
import json
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import html
import logging


class BGGScraper:
    """Scraper for BoardGameGeek.com to extract game information."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Session persists cf_clearance and other Cloudflare cookies across requests
        self._session = requests.Session(impersonate="chrome131")
        self._load_flaresolverr_config()

    def _load_flaresolverr_config(self) -> None:
        """
        Read FlareSolverr proxy settings from the environment.

        FlareSolverr is an optional enhancement: when it is enabled and reachable,
        BGG pages are fetched through its headless browser so Cloudflare challenges
        get solved for us. When it is disabled or fails, the scraper falls back to
        fetching directly with curl_cffi.
        """
        self._flaresolverr_enabled = os.getenv("FLARESOLVERR_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
        self._flaresolverr_url = os.getenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1").strip()
        try:
            # Wall-clock timeout for the HTTP call to the FlareSolverr container
            self._flaresolverr_timeout = float(os.getenv("FLARESOLVERR_TIMEOUT", "90"))
        except ValueError:
            self._flaresolverr_timeout = 90.0
        try:
            # maxTimeout handed to FlareSolverr itself, in milliseconds
            self._flaresolverr_max_timeout = int(os.getenv("FLARESOLVERR_MAX_TIMEOUT", "60000"))
        except ValueError:
            self._flaresolverr_max_timeout = 60000

        if self._flaresolverr_enabled and not self._flaresolverr_url:
            self._flaresolverr_enabled = False

        self.logger.debug(
            f"FlareSolverr {'enabled' if self._flaresolverr_enabled else 'disabled'}"
            + (f" (url: {self._flaresolverr_url})" if self._flaresolverr_enabled else "")
        )

    def _is_bgg_url(self, url: str) -> bool:
        """
        Return True when the URL points at boardgamegeek.com.

        FlareSolverr is only used for BGG pages; Wayback Machine requests are
        always fetched directly.
        """
        try:
            netloc = urlparse(url).netloc.lower()
        except Exception:
            return False
        return netloc == "boardgamegeek.com" or netloc.endswith(".boardgamegeek.com")

    def validate_bgg_url(self, url: str) -> bool:
        """
        Validate that the URL is from boardgamegeek.com.

        Args:
            url: The URL to validate

        Returns:
            True if valid BGG URL, False otherwise
        """
        return True
        try:
            parsed = urlparse(url)
            return "boardgamegeek.com" in parsed.netloc
        except Exception:
            return False

    def extract_bgg_id_from_url(self, url: str) -> Optional[int]:
        """
        Extract the BGG game id from a BoardGameGeek URL.

        Args:
            url: The BoardGameGeek game URL

        Returns:
            The game id if present, otherwise None
        """
        match = re.search(r'boardgamegeek\.com/boardgame/(\d+)', url)
        if not match:
            return None

        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None

    def _fetch_via_flaresolverr(self, url: str) -> Optional[str]:
        """
        Fetch a page through the FlareSolverr container, which solves Cloudflare
        challenges with a real browser and hands back the rendered HTML plus cookies.

        Args:
            url: The URL to fetch

        Returns:
            The HTML content of the page, or None if FlareSolverr could not help
        """
        payload = json.dumps(
            {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": self._flaresolverr_max_timeout,
            }
        ).encode("utf-8")

        request = Request(
            self._flaresolverr_url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._flaresolverr_timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except (URLError, HTTPError, OSError, ValueError) as e:
            self.logger.warning(f"FlareSolverr request to {self._flaresolverr_url} failed: {e}")
            return None

        try:
            result = json.loads(body)
        except json.JSONDecodeError:
            self.logger.warning("FlareSolverr returned a non-JSON response")
            return None

        if result.get("status") != "ok":
            self.logger.warning(f"FlareSolverr reported an error: {result.get('message', 'unknown error')}")
            return None

        solution = result.get("solution") or {}
        status_code = solution.get("status")
        if status_code and int(status_code) in (403, 429, 503):
            self.logger.warning(f"FlareSolverr solved the challenge but BGG still returned {status_code}")
            return None

        # Import the cookies FlareSolverr obtained (cf_clearance etc.) so later
        # direct requests from this scraper can reuse the solved session.
        self._apply_flaresolverr_cookies(solution.get("cookies") or [])

        response_html = solution.get("response")
        if not response_html:
            self.logger.warning("FlareSolverr returned an empty response body")
            return None

        self.logger.info(
            f"FlareSolverr fetched page (status: {status_code}, size: {len(response_html)} bytes)"
        )
        return response_html

    def _apply_flaresolverr_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """
        Copy cookies returned by FlareSolverr into the curl_cffi session.

        Args:
            cookies: The cookie list from a FlareSolverr solution
        """
        applied = 0
        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if not name or value is None:
                continue
            try:
                self._session.cookies.set(
                    name,
                    value,
                    domain=cookie.get("domain") or ".boardgamegeek.com",
                    path=cookie.get("path") or "/",
                )
                applied += 1
            except Exception as e:  # pragma: no cover - defensive, cookie store quirks
                self.logger.debug(f"Could not apply cookie {name}: {e}")
        if applied:
            self.logger.debug(f"Applied {applied} cookie(s) from FlareSolverr")

    def _fetch_web_page(self, url: str) -> str:
        """
        Fetch the HTML content from a URL, preferring the FlareSolverr proxy for
        BoardGameGeek pages and falling back to a direct request.

        Args:
            url: The URL to fetch

        Returns:
            The HTML content of the page

        Raises:
            requests.RequestException: If the request fails
        """
        if self._flaresolverr_enabled and self._is_bgg_url(url):
            solved = self._fetch_via_flaresolverr(url)
            if solved is not None:
                return solved
            self.logger.info(f"Falling back to direct fetch for {url}")

        self.logger.debug(f"Fetching page content from {url}")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._session.get(url, timeout=30)
                if response.status_code in (403, 503):
                    # Cloudflare challenge; wait and retry so the session can accumulate cookies
                    if attempt == max_retries - 1:
                        response.raise_for_status()
                    wait = 2 ** attempt
                    self.logger.warning(f"Cloudflare challenge (status {response.status_code}), retrying in {wait}s")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                self.logger.info(
                    f"Successfully fetched page (status: {response.status_code}, size: {len(response.text)} bytes)"
                )
                return response.text
            except requests.RequestsError as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {e}")
                time.sleep(wait)

    def _parse_image_url(self, html_content: str) -> Optional[str]:
        """
        Parse the HTML content to extract the game cover image URL.

        Replicates: grep preload | grep itemrep | sed -e s/'.*href="'// | sed -e 's/".*$//'

        Args:
            html_content: The HTML content to parse

        Returns:
            The image src URL if found, None otherwise
        """
        # Look for lines containing both "preload" and "itemrep"
        # This replicates: grep preload | grep itemrep
        self.logger.debug("Searching for lines containing 'preload' and 'itemrep'")

        for line in html_content.split("\n"):
            if "preload" in line and "itemrep" in line:
                self.logger.debug(f"Found matching line: {line[:200]}...")

                # Extract href attribute value
                # This replicates: sed -e s/'.*href="'// | sed -e 's/".*$//'
                href_pattern = r'href\s*=\s*"([^"]+)"'
                match = re.search(href_pattern, line, re.IGNORECASE)

                if match:
                    image_url = html.unescape(match.group(1))
                    self.logger.info(
                        f"Successfully extracted href URL: {image_url}"
                    )
                    return image_url

        self.logger.warning("No image found in HTML content")
        return None

    def _parse_game_data(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse the HTML content to extract the GEEK.geekitemPreload JSON data.

        Args:
            html_content: The HTML content to parse

        Returns:
            The parsed JSON data as a Python dict if found, None otherwise
        """
        self.logger.debug("Searching for GEEK.geekitemPreload JSON data")

        for line in html_content.split("\n"):
            if "GEEK.geekitemPreload" in line:
                self.logger.debug(f"Found GEEK.geekitemPreload line: {line[:200]}...")

                # Extract the JSON part: everything between '= ' and the final ';'
                # Pattern: GEEK.geekitemPreload = {json data};
                match = re.search(r'GEEK\.geekitemPreload\s*=\s*({.+});', line, re.IGNORECASE)
                
                if match:
                    json_str = match.group(1)
                    try:
                        game_data = json.loads(json_str)
                        self.logger.info("Successfully parsed GEEK.geekitemPreload JSON data")
                        return game_data
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse JSON: {str(e)}")
                        return None

        self.logger.warning("No GEEK.geekitemPreload data found in HTML content")
        return None

    def get_game_image_url(self, url: str) -> Optional[str]:
        """
        Fetch a BoardGameGeek page and extract the game cover image URL.

        Args:
            url: The BoardGameGeek game URL

        Returns:
            The image src URL if found, None otherwise

        Raises:
            ValueError: If the URL is not a valid BGG URL
            requests.RequestException: If the request fails
        """
        self.logger.info(f"Starting image extraction for URL: {url}")

        try:
            html_content = self._fetch_web_page(url)
            return self._parse_image_url(html_content)
        except requests.RequestsError as e:
            self.logger.error(f"Failed to fetch BGG page {url}: {str(e)}")
            raise requests.RequestsError(f"Failed to fetch BGG page: {str(e)}")

    def get_game_data(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            html_content = self._fetch_web_page(url)
            game_data = self._parse_game_data(html_content)
            if game_data:
                return game_data
            else:
                self.logger.warning(f"No game data found in HTML content for URL: {url}. Falling back to webarchive.")
                return self._get_game_data_webarchive(url)
        except requests.RequestsError as e:
            self.logger.error(f"Failed to fetch BGG page {url}: {str(e)}. Falling back to webarchive.")
        return self._get_game_data_webarchive(url)

    def _get_game_data_webarchive(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a BoardGameGeek page and extract the game data from GEEK.geekitemPreload.

        Args:
            url: The BoardGameGeek game URL

        Returns:
            The parsed game data as a Python dict if found, None otherwise

        Raises:
            ValueError: If the URL is not a valid BGG URL
            requests.RequestException: If the request fails
        """
        self.logger.info(f"Starting game data extraction for URL: {url}")

        try:
            # BGG is sometimes blocking webarchive requests so we have to find the last VALID (HTTP 200) capture of the page
            # We query the CDX API to get the list of archived captures of the BGG page that returned HTTP 200
            # https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server#closest-timestamp-match
            webarchive_capture_json = json.loads(self._fetch_web_page("http://web.archive.org/cdx/search/cdx?output=json&limit=-1&from=2025&filter=statuscode:200&url=" + url))

            # Extract the timestamp of the last valid capture (HTTP 200) from the CDX API response
            timestamp = webarchive_capture_json[1][1] if len(webarchive_capture_json) > 1 and len(webarchive_capture_json[1]) > 1 else None

            # Fetch the archived BGG page from the Wayback Machine using the timestamp of the last valid capture
            html_content = self._fetch_web_page("https://web.archive.org/web/" + timestamp + "/" + url) or ""
            return self._parse_game_data(html_content)
        except requests.RequestsError as e:
            self.logger.error(f"Failed to fetch BGG page {url}: {str(e)}")
            raise requests.RequestsError(f"Failed to fetch BGG page: {str(e)}")

    def _clean_description(self, description: str) -> str:
        """
        Clean HTML tags and entities from game description.

        Args:
            description: Raw description text with HTML

        Returns:
            Cleaned description text
        """
        if not description:
            return ""
        
        # Strip HTML tags
        description = re.sub(r'<[^>]+>', '', description)
        # Replace common HTML entities
        description = re.sub(r'&mdash;', '—', description)
        description = re.sub(r'&nbsp;', ' ', description)
        description = re.sub(r'&[a-z]+;', '', description)  # Remove other HTML entities
        
        return description

    def _extract_rating(self, stats: Dict[str, Any]) -> Optional[float]:
        """
        Extract BGG rating from stats dictionary.

        Args:
            stats: The stats dictionary from game data

        Returns:
            The rating as a float, or None if not found/invalid
        """
        if not stats or 'average' not in stats:
            return None
        
        try:
            return float(stats['average'])
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse rating from stats: {stats.get('average')}")
            return None

    def _extract_basic_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract basic game fields from the item data.

        Args:
            item: The item dictionary from game data

        Returns:
            Dictionary with extracted basic fields

        Raises:
            ValueError: If required fields are missing
        """
        bgg_id = item.get('objectid') or item.get('id')
        title = item.get('name')
        
        if not bgg_id or not title:
            raise ValueError("Missing required fields (objectid or name) in BGG data")
        
        min_players = int(item.get('minplayers', 1))
        max_players = int(item.get('maxplayers', 1))
        image_url = item.get('images', {}).get('thumb', '')

        # Convert urls like https://web.archive.org/web/20251219045944/https://cf.geekdo-images.com/2BZROogBECvPPF2780wlvg__small/img/sdoR62wTU6mKAKrZY96_zhPWy3c=/fit-in/200x150/filters:strip_icc()/pic5521191.jpg
        # to https://cf.geekdo-images.com/2BZROogBECvPPF2780wlvg__small/img/sdoR62wTU6mKAKrZY96_zhPWy3c=/fit-in/200x150/filters:strip_icc()/pic5521191.jpg
        if image_url.startswith("https://web.archive.org/web/"):
            image_url = re.sub(r'^https://web\.archive\.org/web/\d+/', '', image_url) 

        return {
            'bgg_id': int(bgg_id),
            'title': title,
            'min_players': min_players,
            'max_players': max_players,
            'image_url': image_url,
        }

    def extract_game_info(self, game_data: Dict[str, Any], fallback_bgg_url: str = "") -> Dict[str, Any]:
        """
        Extract and process all game information from raw BGG data.

        Args:
            game_data: The raw game data from BGG
            fallback_bgg_url: Fallback URL if canonical_link is not in data

        Returns:
            Dictionary with processed game information

        Raises:
            ValueError: If required data is missing or invalid
        """
        self.logger.info("Extracting game info from BGG data")
        
        # Validate structure
        item = game_data.get('item', {})
        if not item:
            raise ValueError("Invalid game data structure received from BGG")
        
        # Extract basic fields
        basic_info = self._extract_basic_fields(item)
        
        # Extract and clean description
        raw_description = item.get('description', '')
        description = self._clean_description(raw_description)
        short_description = item.get('short_description', description[:2000])  # Truncate if too long
        
        # Extract rating
        stats = item.get('stats', {})
        bgg_rating = self._extract_rating(stats)
        
        # Build complete game info
        game_info = {
            **basic_info,
            'description': description or None,
            'bgg_rating': bgg_rating,
            'bgg_link': fallback_bgg_url,
            'short_description': short_description or None,
            'raw_json': game_data,  # Include raw data for storage
        }
        
        self.logger.info(f"Extracted game info: {game_info['title']} (BGG ID: {game_info['bgg_id']})")
        return game_info
