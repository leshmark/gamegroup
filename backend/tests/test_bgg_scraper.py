import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from curl_cffi import requests
from playwright.sync_api import TimeoutError as BrowserTimeoutError

spec = importlib.util.spec_from_file_location(
    "bgg_scraper", Path(__file__).resolve().parents[1] / "routers/game/bgg_scraper.py"
)
bgg_scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bgg_scraper)
BGGScraper = bgg_scraper.BGGScraper


class FetchWebPageTests(unittest.TestCase):
    url = "https://boardgamegeek.com/boardgame/13/catan"

    def setUp(self):
        self.scraper = BGGScraper()
        self.addCleanup(self.scraper._session.close)
        self.response = MagicMock(status_code=200, text="game HTML", headers={})
        self.get = patch.object(self.scraper._session, "get", return_value=self.response).start()
        self.sleep = patch.object(bgg_scraper.time, "sleep").start()
        self.browser = patch.object(self.scraper, "_fetch_with_browser", return_value="browser HTML").start()
        self.addCleanup(patch.stopall)

    def test_success_uses_http_only(self):
        self.assertEqual(self.scraper._fetch_web_page(self.url), "game HTML")
        self.browser.assert_not_called()

    def test_blocked_status_uses_browser_once_without_http_retries(self):
        for status in (403, 503):
            with self.subTest(status=status):
                self.response.status_code = status
                self.assertEqual(self.scraper._fetch_web_page(self.url), "browser HTML")
        self.assertEqual(self.get.call_count, 2)
        self.assertEqual(self.browser.call_count, 2)
        self.sleep.assert_not_called()

    def test_challenge_header_with_success_status_uses_browser(self):
        self.response.headers = {"cf-mitigated": "challenge"}
        self.assertEqual(self.scraper._fetch_web_page(self.url), "browser HTML")

    def test_challenge_title_with_success_status_uses_browser(self):
        self.response.text = "<html><title>Just a moment...</title></html>"
        self.assertEqual(self.scraper._fetch_web_page(self.url), "browser HTML")

    def test_archive_does_not_launch_browser(self):
        self.response.status_code = 503
        self.response.raise_for_status.side_effect = requests.RequestsError("unavailable")
        with self.assertRaises(requests.RequestsError):
            self.scraper._fetch_web_page("https://web.archive.org/web/20260101/" + self.url)
        self.assertEqual(self.get.call_count, 4)
        self.browser.assert_not_called()

    def test_network_errors_are_retried(self):
        self.get.side_effect = [requests.RequestsError("timeout"), self.response]
        self.assertEqual(self.scraper._fetch_web_page(self.url), "game HTML")
        self.sleep.assert_called_once_with(1)

    def test_browser_failure_preserves_archive_fallback(self):
        self.response.status_code = 403
        self.browser.side_effect = requests.RequestsError("challenge persists")
        with patch.object(self.scraper, "_get_game_data_webarchive", return_value={"item": {}}) as archive:
            self.assertEqual(self.scraper.get_game_data(self.url), {"item": {}})
        archive.assert_called_once_with(self.url)
        self.browser.assert_called_once_with(self.url)


class BrowserFetchTests(unittest.TestCase):
    @patch.dict(bgg_scraper.os.environ, {"BGG_BROWSER_CDP_URL": ""})
    def test_browser_waits_for_content_and_closes_on_success_or_timeout(self):
        for fails in (False, True):
            with self.subTest(fails=fails), patch.object(
                bgg_scraper, "sync_playwright"
            ) as playwright:
                browser = playwright.return_value.__enter__.return_value.chromium.launch.return_value
                page = browser.new_page.return_value
                page.content.return_value = "rendered HTML"
                scraper = BGGScraper()
                self.addCleanup(scraper._session.close)
                if fails:
                    page.wait_for_function.side_effect = BrowserTimeoutError("challenge persists")
                    with self.assertRaises(requests.RequestsError):
                        scraper._fetch_with_browser(FetchWebPageTests.url)
                    page.content.assert_not_called()
                else:
                    self.assertEqual(scraper._fetch_with_browser(FetchWebPageTests.url), "rendered HTML")
                page.wait_for_function.assert_called_once()
                browser.close.assert_called_once()

    @patch.dict(bgg_scraper.os.environ, {"BGG_BROWSER_CDP_URL": "http://127.0.0.1:9222"})
    def test_attached_browser_reuses_context_and_only_closes_its_tab(self):
        for fails in (False, True):
            with self.subTest(fails=fails), patch.object(bgg_scraper, "sync_playwright") as playwright:
                chromium = playwright.return_value.__enter__.return_value.chromium
                browser = chromium.connect_over_cdp.return_value
                page = browser.contexts[0].new_page.return_value
                page.content.return_value = "rendered HTML"
                scraper = BGGScraper()
                self.addCleanup(scraper._session.close)
                if fails:
                    page.wait_for_function.side_effect = BrowserTimeoutError("challenge persists")
                    with self.assertRaises(requests.RequestsError):
                        scraper._fetch_with_browser(FetchWebPageTests.url)
                else:
                    self.assertEqual(scraper._fetch_with_browser(FetchWebPageTests.url), "rendered HTML")
                chromium.connect_over_cdp.assert_called_once_with("http://127.0.0.1:9222", timeout=10_000)
                chromium.launch.assert_not_called()
                page.close.assert_called_once()
                browser.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()