"""ZeroGPT Web Automation Engine using Playwright.

Handles browser launch, Cloudflare challenge detection, multi-selector fallback
interaction, and paragraph paraphrasing with automatic retry.
"""

import logging
import time
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from config import AutomationConfig

logger = logging.getLogger(__name__)


class ZeroGPTAutomation:
    """Manages Playwright browser lifecycle and paraphrasing interactions with ZeroGPT."""

    def __init__(self, config: Optional[AutomationConfig] = None):
        """Initialize automation engine.

        Args:
            config: Optional AutomationConfig instance. Uses defaults if None.
        """
        self.config = config or AutomationConfig()
        self._playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self) -> None:
        """Launch Chromium browser and open initial ZeroGPT page."""
        logger.info("Initializing Playwright and launching Chromium (headless=%s)...", self.config.headless)
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo_ms,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        self.context = self.browser.new_context(
            no_viewport=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.config.timeout_ms)

        logger.info("Navigating to ZeroGPT Paraphraser: %s", self.config.url)
        self.page.goto(self.config.url, wait_until="domcontentloaded")
        self.check_and_handle_cloudflare()

    def check_and_handle_cloudflare(self) -> None:
        """Detect Cloudflare/CAPTCHA challenge screen and prompt user to solve if present."""
        if not self.page:
            return

        is_challenged = False
        for indicator in self.config.cloudflare_indicators:
            try:
                locator = self.page.locator(indicator)
                if locator.count() > 0 and locator.first.is_visible():
                    is_challenged = True
                    break
            except Exception:
                continue

        if is_challenged:
            print("\n" + "=" * 65)
            print("[ATTENTION REQUIRED] Cloudflare / CAPTCHA challenge detected!")
            print("Please complete the verification manually in the browser window.")
            input("Once solved and the paraphraser page is visible, press [ENTER] to resume... ")
            print("Resuming automated paraphrasing pipeline...")
            print("=" * 65 + "\n")
            time.sleep(2)

    def _find_element(self, selectors: list[str], description: str):
        """Find the first matching visible element given a list of fallback selectors."""
        if not self.page:
            raise RuntimeError("Browser page is not initialized.")

        for sel in selectors:
            try:
                locator = self.page.locator(sel)
                if locator.count() > 0:
                    first = locator.first
                    if first.is_visible():
                        logger.debug("Found %s using selector: %s", description, sel)
                        return first
            except Exception as e:
                logger.debug("Selector '%s' check failed for %s: %s", sel, description, e)
                continue

        # If not yet found, wait briefly for the first selector
        try:
            return self.page.wait_for_selector(selectors[0], timeout=5000, state="visible")
        except PlaywrightTimeoutError:
            raise RuntimeError(f"Unable to locate {description} with any configured selector: {selectors}")

    def paraphrase_text(self, text: str) -> str:
        """Submit text to ZeroGPT paraphraser, trigger rewrite, and extract output.

        Args:
            text: Paragraph text to paraphrase.

        Returns:
            Rephrased text output string.

        Raises:
            RuntimeError: If interaction or extraction fails.
        """
        if not self.page:
            raise RuntimeError("Browser is not running. Call start() first.")

        # Ensure Cloudflare hasn't popped up between requests
        self.check_and_handle_cloudflare()

        # Locate input textarea and clear completely
        input_el = self._find_element(self.config.input_selectors, "input textarea")
        input_el.click()
        input_el.fill("")
        time.sleep(0.3)
        input_el.fill(text)
        time.sleep(0.5)

        # Locate and click the action/paraphrase button
        action_btn = self._find_element(self.config.action_selectors, "paraphrase button")
        action_btn.click()
        logger.debug("Clicked paraphrase button. Waiting for output...")

        # Wait for output to populate with rephrased content
        start_wait = time.time()
        timeout_seconds = self.config.timeout_ms / 1000.0
        paraphrased_result = ""

        time.sleep(1.5)  # Allow request to trigger mutation

        while time.time() - start_wait < timeout_seconds:
            try:
                output_el = self._find_element(self.config.output_selectors, "output box")
                content = output_el.input_value() if output_el.evaluate("el => el.tagName") == "TEXTAREA" else output_el.inner_text()
                content = content.strip()
                if content and content != text:
                    paraphrased_result = content
                    break
            except Exception:
                pass
            time.sleep(0.8)

        if not paraphrased_result:
            raise RuntimeError("Paraphraser timed out or did not return distinct rewritten content.")

        # Rate-limiting pause between paragraphs
        time.sleep(self.config.delay_between_requests)
        return paraphrased_result

    def close(self) -> None:
        """Close browser resources and stop Playwright."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self._playwright:
                self._playwright.stop()
            logger.info("Playwright browser closed.")
        except Exception as e:
            logger.warning("Error while closing browser: %s", e)
