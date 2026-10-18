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
        """Strip boilerplate UI buttons, word counts, and labels from humanizer output.

        Only strips lines that are exact short UI label matches (e.g. 'Clear', 'Copy',
        '65 Words'). Actual humanized content is never touched.
        """
        if not text:
            return ""
        import re
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Exact-match UI labels (case-insensitive) that appear as standalone lines
        exact_labels = {
            "clear", "copy", "humanized", "classification",
        }
        # Patterns for short UI label lines (e.g. "65 Words", "AI Probability: 85%")
        label_patterns = [
            re.compile(r'^\d+\s*words?$', re.IGNORECASE),
            re.compile(r'^switch to the advanced model', re.IGNORECASE),
            re.compile(r'^your humanized text will appear here', re.IGNORECASE),
            re.compile(r'^ai probability', re.IGNORECASE),
            re.compile(r'^confidence', re.IGNORECASE),
        ]

        filtered = []
        for line in lines:
            lower = line.lower().strip()
            # Skip single-word exact UI labels
            if lower in exact_labels:
                continue
            # Skip lines matching UI label patterns
            if any(pat.match(lower) for pat in label_patterns):
                continue
            filtered.append(line)
        return "\n\n".join(filtered).strip()


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

        # Step 1: Buffer input - clear browser clipboard so old text can never be mistakenly copied
        try:
            self.page.evaluate("() => navigator.clipboard.writeText('')")
            time.sleep(0.2)
        except Exception:
            pass

        # Keep a Python-side copy of the original input for comparison
        original_input = text

        # Step 2: Clear input field cleanly
        input_el = humanizer_box.locator("textarea.source-textarea, textarea").first
        input_el.fill("", force=True)
        time.sleep(0.2)

        # Clear previous result on page if present
        try:
            clear_btn = humanizer_box.locator(".result-actions :text('Clear'), .text-action:has-text('Clear')")
            if clear_btn.count() > 0 and clear_btn.first.is_visible():
                clear_btn.first.click(no_wait_after=True)
                time.sleep(0.3)
        except Exception:
            pass

        # Step 3: Paste input text from buffer into humanizer textarea
        logger.debug("Pasting buffer into input area (%d characters)...", len(text))
        input_el.fill(text, force=True)
        try:
            input_el.dispatch_event("input")
            input_el.dispatch_event("change")
        except Exception:
            pass
        time.sleep(0.6)

        # Step 4: Click Humanize Text button
        action_btn = humanizer_box.locator("button:has-text('Humanize Text'), button:has-text('Humanize')").first
        action_btn.click(no_wait_after=True)
        logger.info("Clicked 'Humanize Text' button. Waiting for humanization to complete...")

        # Step 5: Wait for generation to complete (observing .result-panel mutation)
        start_wait = time.time()
        timeout_seconds = max(self.config.timeout_ms / 1000.0, 50.0)
        output_buffer = ""

        time.sleep(3.0)  # Initial wait before polling

        while time.time() - start_wait < timeout_seconds:
            try:
                # Check if result panel is populated with new rewritten text
                panel = humanizer_box.locator(".result-panel, .converted-text").first
                panel_text = panel.inner_text().strip() if panel.count() > 0 else ""

                is_ready = (
                    panel_text
                    and "Your humanized text will appear here" not in panel_text
                    and len(panel_text) > 30
                )

                if is_ready:
                    # Strategy A: Click Copy button and read from clipboard into buffer
                    copy_btn = humanizer_box.locator(".result-actions :text('Copy'), .result-panel :text('Copy')").first
                    if copy_btn.count() > 0 and copy_btn.is_visible():
                        try:
                            # Clear clipboard right before clicking Copy
                            self.page.evaluate("() => navigator.clipboard.writeText('')")
                            time.sleep(0.15)
                            copy_btn.click(no_wait_after=True)
                            time.sleep(0.6)
                            clip_text = self.page.evaluate("() => navigator.clipboard.readText()")
                            logger.debug(
                                "Clipboard after Copy click: len=%d, preview=%s",
                                len(clip_text) if clip_text else 0,
                                repr(clip_text[:80]) if clip_text else "(empty)",
                            )
                            if clip_text and clip_text.strip():
                                clip_stripped = clip_text.strip()
                                # Accept as long as the clipboard is non-empty;
                                # the humanizer usually changes something, but even
                                # minor edits are valid output
                                if clip_stripped != original_input:
                                    logger.info("Output buffer captured via Copy button (len=%d).", len(clip_stripped))
                                    output_buffer = clip_stripped
                                    break
                                else:
                                    logger.debug("Clipboard text matches original input; trying panel extraction.")
                        except Exception as e:
                            logger.debug("Clipboard copy read failed: %s", e)

                    # Strategy B: Direct panel extraction into buffer
                    cleaned_panel = self._clean_extracted_text(panel_text)
                    logger.debug(
                        "Panel extraction: raw_len=%d, cleaned_len=%d, preview=%s",
                        len(panel_text),
                        len(cleaned_panel) if cleaned_panel else 0,
                        repr(cleaned_panel[:80]) if cleaned_panel else "(empty)",
                    )
                    if cleaned_panel and len(cleaned_panel) > 20 and cleaned_panel != original_input:
                        logger.info("Output buffer captured from result panel (len=%d).", len(cleaned_panel))
                        output_buffer = cleaned_panel
                        break
            except Exception as exc:
                logger.debug("Polling iteration error: %s", exc)
            time.sleep(1.0)

        if not output_buffer:
            logger.error(
                "Humanizer timed out after %.1fs. No distinct rewritten content found.",
                time.time() - start_wait,
            )
            raise RuntimeError("Humanizer timed out or did not return distinct rewritten content.")

        # Rate-limiting pause
        time.sleep(self.config.delay_between_requests)
        return output_buffer

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
