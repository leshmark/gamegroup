"""BoardGameGeek scraper for extracting game cover images."""

import requests
import re
from typing import Optional
from urllib.parse import urlparse
import html
import logging


class BGGScraper:
    """Scraper for BoardGameGeek.com to extract game information."""
    
    def __init__(self):
        """Initialize the BGG scraper with default headers."""
        self.logger = logging.getLogger(__name__)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def validate_bgg_url(self, url: str) -> bool:
        """
        Validate that the URL is from boardgamegeek.com.
        
        Args:
            url: The URL to validate
            
        Returns:
            True if valid BGG URL, False otherwise
        """
        try:
            parsed = urlparse(url)
            return 'boardgamegeek.com' in parsed.netloc
        except Exception:
            return False
    
    def _extract_attribute(self, img_tag: str, attr_name: str) -> Optional[str]:
        """
        Extract an attribute value from an img tag string.
        
        Args:
            img_tag: The img tag HTML string
            attr_name: The attribute name to extract (e.g., 'src', 'alt')
            
        Returns:
            The attribute value if found, None otherwise
        """
        # Pattern to match the attribute with various quote styles
        pattern = rf'{attr_name}\s*=\s*["\']([^"\'>]+)["\']'
        match = re.search(pattern, img_tag, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1))
        return None
    
    def get_game_image_url(self, url: str) -> Optional[str]:
        """
        Fetch a BoardGameGeek page and extract the game cover image URL.
        
        Replicates: curl <url> | grep preload | grep itemrep | sed -e s/'.*href="'// | sed -e 's/".*$//'
        
        Args:
            url: The BoardGameGeek game URL
            
        Returns:
            The image src URL if found, None otherwise
            
        Raises:
            ValueError: If the URL is not a valid BGG URL
            requests.RequestException: If the request fails
        """
        self.logger.info(f"Starting image extraction for URL: {url}")
        
        if not self.validate_bgg_url(url):
            self.logger.error(f"Invalid BoardGameGeek URL: {url}")
            raise ValueError(f"Invalid BoardGameGeek URL: {url}")
        
        try:
            # Fetch the page
            self.logger.debug(f"Fetching page content from {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            self.logger.info(f"Successfully fetched page (status: {response.status_code}, size: {len(response.text)} bytes)")
            
            html_content = response.text
            
            # Look for lines containing both "preload" and "itemrep"
            # This replicates: grep preload | grep itemrep
            self.logger.debug("Searching for lines containing 'preload' and 'itemrep'")
            
            for line in html_content.split('\n'):
                if 'preload' in line and 'itemrep' in line:
                    self.logger.debug(f"Found matching line: {line[:200]}...")
                    
                    # Extract href attribute value
                    # This replicates: sed -e s/'.*href="'// | sed -e 's/".*$//'
                    href_pattern = r'href\s*=\s*"([^"]+)"'
                    match = re.search(href_pattern, line, re.IGNORECASE)
                    
                    if match:
                        image_url = html.unescape(match.group(1))
                        self.logger.info(f"Successfully extracted href URL: {image_url}")
                        return image_url
            
            self.logger.warning(f"No image found on page: {url}")
            return None
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch BGG page {url}: {str(e)}")
            raise requests.RequestException(f"Failed to fetch BGG page: {str(e)}")
    