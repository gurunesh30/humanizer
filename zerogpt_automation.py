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
            permissions=["clipboard-read", "clipboard-write"],
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

    def _clean_extracted_text(self, text: str) -> str:
        """Strip boilerplate UI buttons, word counts, and labels from humanizer output."""
        if not text:
            return ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        ignored_keywords = [
            "your humanized text will appear here",
            "words",
            "clear",
            "copy",
            "switch to the advanced model",
            "ai probability",
            "confidence",
            "humanized",
            "classification",
        ]
        filtered = []
        for line in lines:
            lower = line.lower()
            if any(kw in lower for kw in ignored_keywords):
                continue
            filtered.append(line)
        return "\n\n".join(filtered).strip()

    def paraphrase_text(self, text: str) -> str:
        """Submit text to ZeroGPT paraphraser/humanizer, trigger rewrite, and extract output.

        Args:
            text: Paragraph text to paraphrase/humanize.

        Returns:
            Rephrased text output string.

        Raises:
            RuntimeError: If interaction or extraction fails.
        """
        if not self.page:
            raise RuntimeError("Browser is not running. Call start() first.")

        # Ensure Cloudflare hasn't popped up between requests
        self.check_and_handle_cloudflare()

        # Handle potential placeholder overlay (e.g. .source-placeholder)
        try:
            placeholder = self.page.locator(".source-placeholder, .panel-placeholder")
            if placeholder.count() > 0 and placeholder.first.is_visible():
                placeholder.first.click(force=True)
                time.sleep(0.3)
        except Exception:
            pass

        # Clear existing text using keyboard and fill
        input_el = self._find_element(self.config.input_selectors, "input textarea")
        try:
            input_el.click(force=True)
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
        except Exception:
            pass
        input_el.fill("", force=True)
        time.sleep(0.3)

        # Clear button on page if present (to reset previous paragraph's output/input)
        try:
            clear_btn = self.page.locator("button:has-text('Clear'), span:has-text('Clear'), div:has-text('Clear')")
            if clear_btn.count() > 0 and clear_btn.first.is_visible():
                clear_btn.first.click(force=True)
                time.sleep(0.4)
        except Exception:
            pass

        # Paste/inject paragraph text into textarea and dispatch input events
        logger.debug("Pasting paragraph into input area (%d characters)...", len(text))
        input_el.click(force=True)
        input_el.fill(text, force=True)
        # Dispatch reactive events so Vue updates character count and enables the button
        try:
            input_el.dispatch_event("input")
            input_el.dispatch_event("change")
        except Exception:
            pass
        time.sleep(0.8)

        # Locate and click the action/humanize button
        action_btn = self._find_element(self.config.action_selectors, "action button")
        action_btn.click(force=True)
        logger.info("Clicked 'Humanize Text' button. Waiting for humanization to complete...")

        # Wait for generation to complete (ZeroGPT humanizer typically takes 15-25 seconds)
        start_wait = time.time()
        timeout_seconds = max(self.config.timeout_ms / 1000.0, 45.0)
        paraphrased_result = ""

        time.sleep(3.0)  # Initial wait before polling

        while time.time() - start_wait < timeout_seconds:
            try:
                # Priority 1: Check if "Copy" button is present and active in the output area
                copy_btns = self.page.locator("button:has-text('Copy'), div:has-text('Copy'), span:has-text('Copy')")
                if copy_btns.count() > 0:
                    for i in range(copy_btns.count()):
                        btn = copy_btns.nth(i)
                        if btn.is_visible():
                            try:
                                btn.click(force=True)
                                time.sleep(0.4)
                                # Read text directly from browser clipboard
                                clip_text = self.page.evaluate("navigator.clipboard.readText()")
                                if clip_text and clip_text.strip() and clip_text.strip() != text:
                                    cleaned_clip = self._clean_extracted_text(clip_text.strip())
                                    if cleaned_clip and len(cleaned_clip) > 15:
                                        logger.info("Successfully copied humanized text via Copy button!")
                                        paraphrased_result = cleaned_clip
                                        break
                            except Exception as e:
                                logger.debug("Clipboard copy read failed: %s", e)
                    if paraphrased_result:
                        break

                # Priority 2: Extract from .converted-text or .result-panel
                conv_loc = self.page.locator(".converted-text, .result-panel")
                if conv_loc.count() > 0:
                    raw_content = conv_loc.first.inner_text().strip()
                    cleaned = self._clean_extracted_text(raw_content)
                    if cleaned and len(cleaned) > 20 and cleaned != text:
                        paraphrased_result = cleaned
                        break

                # Priority 3: Fallback output selectors
                output_el = self._find_element(self.config.output_selectors, "output box")
                tag_name = output_el.evaluate("el => el.tagName")
                raw_content = output_el.input_value() if tag_name == "TEXTAREA" else output_el.inner_text()
                cleaned = self._clean_extracted_text(raw_content)
                if cleaned and len(cleaned) > 20 and cleaned != text:
                    paraphrased_result = cleaned
                    break
            except Exception:
                pass
            time.sleep(1.0)

        if not paraphrased_result:
            raise RuntimeError("Humanizer timed out or did not return distinct rewritten content.")

        # Rate-limiting pause between paragraphs
        time.sleep(self.config.delay_between_requests)
        return paraphrased_result

    def paraphrase_with_retry(self, text: str, max_retries: Optional[int] = None) -> tuple[str, bool]:
        """Paraphrase text with retry loop and exponential backoff.

        If all retries fail, returns the original text to ensure document integrity.

        Args:
            text: Paragraph text.
            max_retries: Maximum number of attempts. Defaults to config.max_retries.

        Returns:
            Tuple of (resulting_text, was_paraphrased_successfully).
        """
        retries = max_retries if max_retries is not None else self.config.max_retries
        for attempt in range(1, retries + 1):
            try:
                result = self.paraphrase_text(text)
                return result, True
            except Exception as e:
                logger.warning(
                    "Attempt %d/%d failed to paraphrase paragraph: %s",
                    attempt,
                    retries,
                    e,
                )
                if attempt < retries:
                    backoff = attempt * 2.0
                    logger.info("Backing off for %.1f seconds before retry...", backoff)
                    time.sleep(backoff)
                else:
                    logger.error(
                        "All %d attempts failed for paragraph. Falling back to original text.",
                        retries,
                    )
                    return text, False

        return text, False

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
