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
            viewport={"width": 1400, "height": 900},
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
        # Ensure page stays at the top without auto-scrolling
        try:
            self.page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
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
    def _single_humanize_pass(self, text: str) -> str:
        """Perform a single humanization pass on text without unnecessary page scrolling."""
        if not self.page:
            raise RuntimeError("Browser is not running. Call start() first.")

        # Keep viewport at the top of the humanizer box
        try:
            self.page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        self.check_and_handle_cloudflare()

        # Target textarea strictly within .ai-humanizer to prevent outside clicks
        humanizer_box = self.page.locator(".ai-humanizer")
        if humanizer_box.count() == 0:
            humanizer_box = self.page.locator("body")

        # Check and handle placeholder overlay
        try:
            placeholder = humanizer_box.locator(".source-placeholder, .paste-action")
            if placeholder.count() > 0 and placeholder.first.is_visible():
                placeholder.first.click(no_wait_after=True)
                time.sleep(0.3)
        except Exception:
            pass

        # Locate textarea inside humanizer box
        input_el = humanizer_box.locator("textarea.source-textarea, textarea").first
        try:
            input_el.click(no_wait_after=True)
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
        except Exception:
            pass
        input_el.fill("", force=True)
        time.sleep(0.2)

        # Clear button on page if present (to reset previous paragraph's output/input)
        try:
            clear_btn = humanizer_box.locator(".result-actions :text('Clear'), .text-action:has-text('Clear')")
            if clear_btn.count() > 0 and clear_btn.first.is_visible():
                clear_btn.first.click(no_wait_after=True)
                time.sleep(0.3)
        except Exception:
            pass

        # Paste/inject paragraph text into textarea and dispatch input events
        logger.debug("Pasting text into input area (%d characters)...", len(text))
        input_el.fill(text, force=True)
        try:
            input_el.dispatch_event("input")
            input_el.dispatch_event("change")
        except Exception:
            pass
        time.sleep(0.6)

        # Locate and click the action/humanize button inside humanizer box
        action_btn = humanizer_box.locator("button:has-text('Humanize Text'), button:has-text('Humanize')").first
        action_btn.click(no_wait_after=True)
        logger.info("Clicked 'Humanize Text' button. Waiting for humanization to complete...")

        # Wait for generation to complete
        start_wait = time.time()
        timeout_seconds = max(self.config.timeout_ms / 1000.0, 45.0)
        paraphrased_result = ""

        time.sleep(3.0)  # Initial wait before polling

        while time.time() - start_wait < timeout_seconds:
            try:
                # Priority 1: Check if "Copy" action is available inside the result panel
                copy_action = humanizer_box.locator(".result-actions, .result-action-buttons, .result-panel").locator(":text('Copy')")
                if copy_action.count() > 0 and copy_action.first.is_visible():
                    try:
                        copy_action.first.click(no_wait_after=True)
                        time.sleep(0.4)
                        clip_text = self.page.evaluate("navigator.clipboard.readText()")
                        if clip_text and clip_text.strip() and clip_text.strip() != text:
                            cleaned_clip = self._clean_extracted_text(clip_text.strip())
                            if cleaned_clip and len(cleaned_clip) > 15:
                                logger.info("Copied humanized text via Copy button.")
                                paraphrased_result = cleaned_clip
                                break
                    except Exception as e:
                        logger.debug("Clipboard copy read failed: %s", e)

                # Priority 2: Extract text directly from .converted-text or .result-panel
                conv_loc = humanizer_box.locator(".converted-text, .result-panel")
                if conv_loc.count() > 0:
                    raw_content = conv_loc.first.inner_text().strip()
                    cleaned = self._clean_extracted_text(raw_content)
                    if cleaned and len(cleaned) > 20 and cleaned != text:
                        paraphrased_result = cleaned
                        break
            except Exception:
                pass
            time.sleep(1.0)

        if not paraphrased_result:
            raise RuntimeError("Humanizer timed out or did not return distinct rewritten content.")

        # Rate-limiting pause
        time.sleep(self.config.delay_between_requests)
        return paraphrased_result

    def paraphrase_text(self, text: str, passes: Optional[int] = None) -> str:
        """Paraphrase/humanize text across multiple passes if specified.

        For example, if passes=2:
          Pass 1: Takes original docx paragraph -> Humanizes -> Copies output.
          Pass 2: Takes Pass 1 output -> Humanizes -> Copies final output.

        Args:
            text: Initial paragraph text.
            passes: Number of sequential humanization passes (defaults to config.passes).

        Returns:
            Final humanized text string after all passes.
        """
        total_passes = passes if (passes is not None and passes > 0) else self.config.passes
        current_text = text

        for p_idx in range(1, total_passes + 1):
            if total_passes > 1:
                logger.info("Executing humanize pass %d/%d for paragraph...", p_idx, total_passes)
            current_text = self._single_humanize_pass(current_text)

        return current_text

    def paraphrase_with_retry(
        self, text: str, max_retries: Optional[int] = None, passes: Optional[int] = None
    ) -> tuple[str, bool]:
        """Paraphrase text with retry loop and exponential backoff across all passes.

        If all retries fail, returns the original text to ensure document integrity.

        Args:
            text: Paragraph text.
            max_retries: Maximum number of attempts. Defaults to config.max_retries.
            passes: Number of humanize iterations (e.g. 2 for 2-pass humanization).

        Returns:
            Tuple of (resulting_text, was_paraphrased_successfully).
        """
        retries = max_retries if max_retries is not None else self.config.max_retries
        for attempt in range(1, retries + 1):
            try:
                result = self.paraphrase_text(text, passes=passes)
                return result, True
            except Exception as e:
                logger.warning(
                    "Attempt %d/%d failed to humanize paragraph: %s",
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
