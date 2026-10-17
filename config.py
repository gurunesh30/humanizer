"""Configuration, selectors, and options for ZeroGPT paraphrasing automation."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class AutomationConfig:
    """Configuration settings for browser automation and anti-bot mitigation."""

    url: str = "https://www.zerogpt.com/ai-humanizer"
    headless: bool = False
    delay_between_requests: float = 4.0  # Configurable 3-5s rate limit delay
    max_retries: int = 3
    timeout_ms: int = 30000
    slow_mo_ms: int = 100

    # Fallback CSS selectors for resilient page interaction
    input_selectors: List[str] = field(
        default_factory=lambda: [
            "textarea.source-textarea",
            "textarea#input-text",
            "textarea[placeholder*='text' i]",
            "textarea[placeholder*='humanize' i]",
            "textarea[placeholder*='paraphrase' i]",
            "textarea.paraphrase-input",
            "textarea",
        ]
    )

    action_selectors: List[str] = field(
        default_factory=lambda: [
            "button:has-text('Humanize Text')",
            "button:has-text('Humanize')",
            "button:has-text('Paraphrase')",
            "button:has-text('Rewrite')",
            "button:has-text('Paraphrase Text')",
            "button.btn-primary",
            "button[type='submit']",
        ]
    )

    output_selectors: List[str] = field(
        default_factory=lambda: [
            ".converted-text",
            ".result-panel",
            ".output-text",
            "#output-text",
            "div.paraphrase-output",
            "div[class*='output']",
            "div[id*='output']",
            "textarea[readonly]",
        ]
    )

    cloudflare_indicators: List[str] = field(
        default_factory=lambda: [
            "text='Verify you are human'",
            "text='Checking your browser before accessing'",
            "text='Just a moment...'",
            "iframe[src*='challenges.cloudflare.com']",
            "iframe[src*='turnstile']",
            "#challenge-stage",
            "#cf-challenge-running",
        ]
    )
