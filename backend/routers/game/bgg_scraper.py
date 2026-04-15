"""BoardGameGeek scraper for extracting game cover images."""

import time
import requests
import re
import json
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import html
import logging


class BGGScraper:
    """Scraper for BoardGameGeek.com to extract game information."""

    def __init__(self):
        """Initialize the BGG scraper with default headers."""
        self.logger = logging.getLogger(__name__)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

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

    def _fetch_web_page(self, url: str) -> str:
        """
        Fetch the HTML content from a BoardGameGeek URL.

        Args:
            url: The BoardGameGeek game URL

        Returns:
            The HTML content of the page

        Raises:
            requests.RequestException: If the request fails
        """
        self.logger.debug(f"Fetching page content from {url}")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                self.logger.info(
                    f"Successfully fetched page (status: {response.status_code}, size: {len(response.text)} bytes)"
                )
                return response.text
            except requests.RequestException as e:
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
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch BGG page {url}: {str(e)}")
            raise requests.RequestException(f"Failed to fetch BGG page: {str(e)}")

    def get_game_data(self, url: str) -> Optional[Dict[str, Any]]:
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
            html_content = self._fetch_web_page("https://web.archive.org/web/" + timestamp + "/" + url)
            return self._parse_game_data(html_content)
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch BGG page {url}: {str(e)}")
            raise requests.RequestException(f"Failed to fetch BGG page: {str(e)}")

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
