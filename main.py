"""Command-Line Interface for ZeroGPT Word Document Paraphrasing Automation Pipeline.

Usage:
    python main.py --input sample.docx --output paraphrased_output.docx
    python main.py -i input.docx -o output.docx --delay 3.5 --retries 3
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from config import AutomationConfig
from doc_handler import DocumentHandler

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ZeroGPTPipeline")


def parse_arguments() -> argparse.Namespace:
    """Parse and validate CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="humanizer",
        description="Automated Word Document Paraphraser using ZeroGPT & Playwright",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=str,
        help="Path to the input Microsoft Word document (.docx)",
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=str,
        help="Path where the paraphrased Microsoft Word document (.docx) will be saved",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=4.0,
        help="Delay in seconds between consecutive paragraph submissions for rate-limit mitigation",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retry attempts per paragraph on network or selector timeouts",
    )

    parser.add_argument(
        "--passes",
        type=int,
        default=1,
        help="Number of sequential humanization passes per paragraph (e.g. 2 to humanize the humanized output)",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (NOTE: headless=False is recommended for Cloudflare handling)",
    )

    parser.add_argument(
        "--url",
        type=str,
        default="https://www.zerogpt.com/ai-humanizer",
        help="Target ZeroGPT endpoint URL (defaults to AI Humanizer)",
    )

    return parser.parse_args()


def run_pipeline(
    input_file: str,
    output_file: str,
    delay: float = 4.0,
    retries: int = 3,
    passes: int = 1,
    headless: bool = False,
    url: Optional[str] = None,
) -> int:
    """Execute the end-to-end paraphrasing pipeline.

    Args:
        input_file: Source .docx path.
        output_file: Destination .docx path.
        delay: Pause between paragraph queries.
        retries: Retries per paragraph.
        passes: Number of sequential humanization passes per paragraph.
        headless: Whether browser is headless.
        url: Paraphraser URL.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return 1

    if input_path.suffix.lower() != ".docx":
        logger.error("Input file must be a .docx document: %s", input_path)
        return 1

    logger.info("Initializing document handler...")
    doc_handler = DocumentHandler(input_path=str(input_path), output_path=str(output_path))

    try:
        paragraphs = doc_handler.read_paragraphs()
    except Exception as e:
        logger.error("Failed to read input document: %s", e)
        return 1

    total = len(paragraphs)
    if total == 0:
        logger.warning("No non-empty paragraphs found in the input document.")
        return 0

    logger.info("Found %d non-empty paragraph(s) to process.", total)

    # Initialize target output file (incremental save target)
    doc_handler.init_output_document()
    logger.info("Initialized output document at: %s", output_path)

    # Configure automation engine
    config = AutomationConfig(
        headless=headless,
        delay_between_requests=delay,
        max_retries=retries,
        passes=passes,
    )
    if url:
        config.url = url

    try:
        from zerogpt_automation import ZeroGPTAutomation
    except ImportError:
        logger.error(
            "Playwright is not installed. Please run: pip install -r requirements.txt && playwright install chromium"
        )
        return 1

    automation = ZeroGPTAutomation(config=config)
    success_count = 0
    fallback_count = 0

    try:
        automation.start()
        print("\n" + "=" * 65)
        print("  ZeroGPT Word Document Paraphraser Pipeline Started")
        print(f"  Input:  {input_path}")
        print(f"  Output: {output_path}")
        print(f"  Total Paragraphs: {total}")
        print(f"  Humanize Passes:  {passes}")
        print("=" * 65 + "\n")

        for idx, paragraph in enumerate(paragraphs, start=1):
            logger.info("Processing paragraph %d/%d (%d characters, %d pass(es))...", idx, total, len(paragraph), passes)
            result_text, ok = automation.paraphrase_with_retry(paragraph, passes=passes)

            if ok:
                success_count += 1
                logger.info("Paragraph %d/%d successfully paraphrased.", idx, total)
            else:
                fallback_count += 1
                logger.warning(
                    "Paragraph %d/%d fallback to original paragraph due to error.",
                    idx,
                    total,
                )

            # Incrementally write and flush to disk
            doc_handler.append_paragraph(result_text)
            logger.info("Paragraph %d/%d saved to %s", idx, total, output_path.name)

        print("\n" + "=" * 65)
        print("Pipeline Execution Completed Successfully!")
        print(f"  Total Processed: {total}")
        print(f"  Paraphrased:     {success_count}")
        print(f"  Fallbacks:       {fallback_count}")
        print(f"  Saved File:      {output_path.resolve()}")
        print("=" * 65 + "\n")

    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user! Existing progress saved to %s", output_path)
        return 130
    except Exception as e:
        logger.error("Pipeline encountered an unexpected error: %s", e, exc_info=True)
        return 1
    finally:
        automation.close()

    return 0


def main() -> None:
    """CLI Entry point."""
    args = parse_arguments()
    code = run_pipeline(
        input_file=args.input,
        output_file=args.output,
        delay=args.delay,
        retries=args.retries,
        passes=args.passes,
        headless=args.headless,
        url=args.url,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
