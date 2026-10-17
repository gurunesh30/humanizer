import sys
from pathlib import Path

# Ensure workspace root is in python path
sys.path.insert(0, str(Path(__file__).parent))

from config import AutomationConfig


def test_default_config_initialization():
    cfg = AutomationConfig()
    assert cfg.url == "https://www.zerogpt.com/ai-humanizer"
    assert cfg.headless is False
    assert 3.0 <= cfg.delay_between_requests <= 5.0
    assert cfg.max_retries == 3
    assert len(cfg.input_selectors) > 0
    assert len(cfg.action_selectors) > 0
    assert len(cfg.output_selectors) > 0
    assert len(cfg.cloudflare_indicators) > 0


def test_custom_config_override():
    cfg = AutomationConfig(
        url="https://custom-url.com",
        headless=True,
        delay_between_requests=5.0,
        max_retries=5,
    )
    assert cfg.url == "https://custom-url.com"
    assert cfg.headless is True
    assert cfg.delay_between_requests == 5.0
    assert cfg.max_retries == 5


if __name__ == "__main__":
    test_default_config_initialization()
    test_custom_config_override()
    print("All config tests passed!")
