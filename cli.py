"""Interactive CLI module for the ZeroGPT Humanizer Pipeline.

Provides a rich, guided selection flow when run without arguments,
and maintains backward-compatible argparse for scripting use.
"""

import glob
import os
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box
import questionary
from questionary import Style

console = Console()

# ─── Questionary theme ────────────────────────────────────────────────────────
CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:#a855f7 bold"),       # purple question mark
        ("question", "fg:#e2e8f0 bold"),     # light text
        ("answer", "fg:#22d3ee bold"),       # cyan answer
        ("pointer", "fg:#a855f7 bold"),      # purple pointer ›
        ("highlighted", "fg:#a855f7 bold"),  # selected highlight
        ("selected", "fg:#22d3ee"),          # chosen item
        ("separator", "fg:#6b7280"),         # dimmed separator
        ("instruction", "fg:#9ca3af italic"),
        ("text", "fg:#e2e8f0"),
        ("disabled", "fg:#4b5563 italic"),
    ]
)


# ─── Banner ───────────────────────────────────────────────────────────────────

BANNER = r"""
[bold cyan]  ╦ ╦╦ ╦╔╦╗╔═╗╔╗╔╦╔═╗╔═╗╦═╗[/]
[bold cyan]  ╠═╣║ ║║║║╠═╣║║║║╔═╝║╣ ╠╦╝[/]
[bold cyan]  ╩ ╩╚═╝╩ ╩╩ ╩╝╚╝╩╚═╝╚═╝╩╚═[/]
[dim]  ──────────────────────────────[/]
[dim italic]  AI-Powered Document Humanizer[/]
[dim italic]  ZeroGPT Automation Pipeline[/]
"""


def show_banner() -> None:
    """Display the application banner."""
    console.print(
        Panel(
            BANNER,
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
            padding=(0, 2),
        )
    )
    console.print()


# ─── File Discovery ──────────────────────────────────────────────────────────

def discover_docx_files(directory: str = ".") -> list[str]:
    """Find all .docx files in the given directory (non-recursive)."""
    pattern = os.path.join(directory, "*.docx")
    files = sorted(glob.glob(pattern))
    # Filter out temp files (e.g. ~$file.docx)
    return [f for f in files if not os.path.basename(f).startswith("~$")]


def suggest_output_name(input_path: str) -> str:
    """Generate a smart default output filename based on the input file."""
    p = Path(input_path)
    stem = p.stem
    # Avoid doubling the suffix
    if stem.endswith("_humanized"):
        return str(p)
    return str(p.parent / f"{stem}_humanized{p.suffix}")


# ─── Interactive Wizard ──────────────────────────────────────────────────────

def run_interactive_wizard() -> dict:
    """Run the full interactive configuration wizard.

    Returns:
        Dictionary of pipeline configuration parameters.
    """
    show_banner()

    # ── Step 1: Input File ────────────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]Step 1[/]  Select Input Document", style="bright_cyan"))
    console.print()

    docx_files = discover_docx_files()

    if docx_files:
        # Show available files as selectable choices + manual entry option
        choices = [
            questionary.Choice(
                title=f"📄 {os.path.basename(f)}  [dim]({os.path.getsize(f) / 1024:.1f} KB)[/dim]"
                    if False else f"📄 {os.path.basename(f)}  ({os.path.getsize(f) / 1024:.1f} KB)",
                value=f,
            )
            for f in docx_files
        ]
        choices.append(questionary.Choice(title="📂 Enter a custom file path...", value="__custom__"))

        input_file = questionary.select(
            "Choose the input .docx file:",
            choices=choices,
            style=CUSTOM_STYLE,
            qmark="›",
            instruction="(↑↓ to navigate, Enter to select)",
        ).ask()

        if input_file is None:
            _abort()

        if input_file == "__custom__":
            input_file = questionary.path(
                "Enter the path to your .docx file:",
                style=CUSTOM_STYLE,
                qmark="›",
                validate=lambda p: (
                    True if p.strip().lower().endswith(".docx") and Path(p.strip()).exists()
                    else "File must be an existing .docx document"
                ),
            ).ask()
            if input_file is None:
                _abort()
    else:
        console.print("[dim italic]  No .docx files found in current directory.[/]\n")
        input_file = questionary.path(
            "Enter the path to your .docx file:",
            style=CUSTOM_STYLE,
            qmark="›",
            validate=lambda p: (
                True if p.strip().lower().endswith(".docx") and Path(p.strip()).exists()
                else "File must be an existing .docx document"
            ),
        ).ask()
        if input_file is None:
            _abort()

    input_file = input_file.strip()
    console.print(f"  [green]✓[/] Input: [bold]{input_file}[/]\n")

    # ── Step 2: Output File ───────────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]Step 2[/]  Set Output Document", style="bright_cyan"))
    console.print()

    default_output = suggest_output_name(input_file)

    output_choice = questionary.select(
        "Where should the humanized document be saved?",
        choices=[
            questionary.Choice(
                title=f"💾 Default: {os.path.basename(default_output)}",
                value=default_output,
            ),
            questionary.Choice(title="✏️  Enter a custom output path...", value="__custom__"),
        ],
        style=CUSTOM_STYLE,
        qmark="›",
    ).ask()

    if output_choice is None:
        _abort()

    if output_choice == "__custom__":
        output_file = questionary.text(
            "Enter the output .docx file path:",
            default=default_output,
            style=CUSTOM_STYLE,
            qmark="›",
            validate=lambda p: (
                True if p.strip().lower().endswith(".docx")
                else "Output file must end with .docx"
            ),
        ).ask()
        if output_file is None:
            _abort()
    else:
        output_file = output_choice

    output_file = output_file.strip()
    console.print(f"  [green]✓[/] Output: [bold]{output_file}[/]\n")

    # ── Step 3: Humanization Passes ───────────────────────────────────────
    console.print(Rule("[bold bright_cyan]Step 3[/]  Humanization Strength", style="bright_cyan"))
    console.print()

    passes_choice = questionary.select(
        "How many humanization passes per paragraph?",
        choices=[
            questionary.Choice(title="1 pass  — Quick, light rewrite", value=1),
            questionary.Choice(title="2 passes — Recommended, deeper humanization", value=2),
            questionary.Choice(title="3 passes — Heavy rewrite, maximum change", value=3),
            questionary.Choice(title="4 passes — Ultra-deep (slower)", value=4),
            questionary.Choice(title="5 passes — Maximum (very slow)", value=5),
            questionary.Choice(title="✏️  Custom number of passes...", value=-1),
        ],
        default=2,
        style=CUSTOM_STYLE,
        qmark="›",
        instruction="(more passes = more human-like, but slower)",
    ).ask()

    if passes_choice is None:
        _abort()

    if passes_choice == -1:
        passes_str = questionary.text(
            "Enter number of passes (e.g. 2):",
            default="2",
            style=CUSTOM_STYLE,
            qmark="›",
            validate=lambda v: True if _is_positive_int(v) else "Must be a positive integer (e.g. 1, 2, 3)",
        ).ask()
        if passes_str is None:
            _abort()
        passes = int(passes_str)
    else:
        passes = passes_choice

    console.print(f"  [green]✓[/] Passes: [bold]{passes}[/]\n")

    # ── Step 4: Advanced Settings ─────────────────────────────────────────
    console.print(Rule("[bold bright_cyan]Step 4[/]  Advanced Settings", style="bright_cyan"))
    console.print()

    customize = questionary.confirm(
        "Customize advanced settings? (delay, retries, headless, URL)",
        default=False,
        style=CUSTOM_STYLE,
        qmark="›",
    ).ask()

    if customize is None:
        _abort()

    delay = 4.0
    retries = 3
    headless = False
    url = "https://www.zerogpt.com/ai-humanizer"

    if customize:
        console.print()

        # Delay
        delay_choice = questionary.select(
            "Delay between paragraph requests:",
            choices=[
                questionary.Choice(title="⚡ 2 seconds  — Fast (may trigger rate limits)", value=2.0),
                questionary.Choice(title="🔄 4 seconds  — Balanced (recommended)", value=4.0),
                questionary.Choice(title="🐢 6 seconds  — Safe (for large documents)", value=6.0),
                questionary.Choice(title="🛡️  10 seconds — Very safe (for unstable connections)", value=10.0),
                questionary.Choice(title="✏️  Custom value...", value=-1.0),
            ],
            default=4.0,
            style=CUSTOM_STYLE,
            qmark="›",
        ).ask()

        if delay_choice is None:
            _abort()

        if delay_choice == -1.0:
            delay_str = questionary.text(
                "Enter delay in seconds (e.g. 3.5):",
                default="4.0",
                style=CUSTOM_STYLE,
                qmark="›",
                validate=lambda v: True if _is_positive_float(v) else "Must be a positive number",
            ).ask()
            if delay_str is None:
                _abort()
            delay = float(delay_str)
        else:
            delay = delay_choice

        # Retries
        retries_choice = questionary.select(
            "Max retries per paragraph on failure:",
            choices=[
                questionary.Choice(title="1 retry  — Fail fast", value=1),
                questionary.Choice(title="3 retries — Recommended", value=3),
                questionary.Choice(title="5 retries — Persistent", value=5),
                questionary.Choice(title="10 retries — Very persistent", value=10),
            ],
            default=3,
            style=CUSTOM_STYLE,
            qmark="›",
        ).ask()

        if retries_choice is None:
            _abort()
        retries = retries_choice

        # Headless
        headless = questionary.confirm(
            "Run browser in headless mode? (hidden window, faster but can't solve CAPTCHAs)",
            default=False,
            style=CUSTOM_STYLE,
            qmark="›",
        ).ask()

        if headless is None:
            _abort()

        # URL
        change_url = questionary.confirm(
            "Use a custom humanizer URL? (default: zerogpt.com/ai-humanizer)",
            default=False,
            style=CUSTOM_STYLE,
            qmark="›",
        ).ask()

        if change_url is None:
            _abort()

        if change_url:
            url = questionary.text(
                "Enter the humanizer URL:",
                default=url,
                style=CUSTOM_STYLE,
                qmark="›",
            ).ask()
            if url is None:
                _abort()

    console.print(f"  [green]✓[/] Delay: [bold]{delay}s[/]  |  Retries: [bold]{retries}[/]  |  Headless: [bold]{headless}[/]\n")

    # ── Step 5: Confirmation ──────────────────────────────────────────────
    config = {
        "input": input_file,
        "output": output_file,
        "passes": passes,
        "delay": delay,
        "retries": retries,
        "headless": headless,
        "url": url,
    }

    _show_config_summary(config)

    proceed = questionary.confirm(
        "Start the humanization pipeline?",
        default=True,
        style=CUSTOM_STYLE,
        qmark="›",
    ).ask()

    if not proceed:
        _abort()

    console.print()
    return config


# ─── Display Helpers ──────────────────────────────────────────────────────────

def _show_config_summary(config: dict) -> None:
    """Render a styled configuration summary table."""
    table = Table(
        title="Pipeline Configuration",
        box=box.ROUNDED,
        title_style="bold bright_cyan",
        border_style="bright_cyan",
        header_style="bold white",
        show_lines=True,
        padding=(0, 2),
    )
    table.add_column("Setting", style="dim", width=22)
    table.add_column("Value", style="bold white")

    table.add_row("📄 Input File", os.path.basename(config["input"]))
    table.add_row("💾 Output File", os.path.basename(config["output"]))
    table.add_row("🔄 Passes", str(config["passes"]))
    table.add_row("⏱️  Delay", f"{config['delay']}s")
    table.add_row("🔁 Retries", str(config["retries"]))
    table.add_row("👁️  Headless", "Yes" if config["headless"] else "No")
    table.add_row("🌐 URL", config["url"])

    console.print()
    console.print(table)
    console.print()


def show_pipeline_header(config: dict, total_paragraphs: int) -> None:
    """Display a styled pipeline start header."""
    header = Text.assemble(
        ("  ZeroGPT Humanizer Pipeline\n", "bold bright_cyan"),
        (f"  {os.path.basename(config['input'])}", "bold white"),
        (" → ", "dim"),
        (f"{os.path.basename(config['output'])}\n", "bold green"),
        (f"  {total_paragraphs} paragraphs", "white"),
        (" × ", "dim"),
        (f"{config['passes']} pass{'es' if config['passes'] > 1 else ''}", "white"),
    )
    console.print(
        Panel(header, border_style="bright_cyan", box=box.HEAVY, padding=(1, 2))
    )
    console.print()


def show_paragraph_progress(idx: int, total: int, status: str, detail: str = "") -> None:
    """Display paragraph processing status."""
    if status == "processing":
        console.print(
            f"  [bright_cyan]⟳[/] [{idx}/{total}] Processing paragraph... [dim]{detail}[/]"
        )
    elif status == "success":
        console.print(
            f"  [green]✓[/] [{idx}/{total}] Humanized successfully [dim]{detail}[/]"
        )
    elif status == "fallback":
        console.print(
            f"  [yellow]⚠[/] [{idx}/{total}] Fallback to original [dim]{detail}[/]"
        )
    elif status == "pass":
        console.print(
            f"    [dim cyan]↻[/] [dim]{detail}[/]"
        )


def show_pipeline_summary(total: int, success: int, fallback: int, elapsed: float, output_path: str) -> None:
    """Display the final pipeline summary."""
    console.print()

    # Summary table
    table = Table(
        title="Pipeline Results",
        box=box.ROUNDED,
        title_style="bold bright_green",
        border_style="bright_green",
        header_style="bold white",
        show_lines=True,
        padding=(0, 2),
    )
    table.add_column("Metric", style="dim", width=22)
    table.add_column("Value", style="bold white")

    table.add_row("📊 Total Paragraphs", str(total))
    table.add_row("✅ Humanized", f"[green]{success}[/]")
    if fallback > 0:
        table.add_row("⚠️  Fallbacks", f"[yellow]{fallback}[/]")
    else:
        table.add_row("⚠️  Fallbacks", f"[dim]{fallback}[/]")
    table.add_row("⏱️  Time Elapsed", f"{elapsed:.1f}s")
    table.add_row("💾 Output File", os.path.basename(output_path))

    # Success rate bar
    rate = (success / total * 100) if total > 0 else 0
    bar_filled = int(rate / 5)
    bar_empty = 20 - bar_filled
    bar = f"[green]{'█' * bar_filled}[/][dim]{'░' * bar_empty}[/] {rate:.0f}%"
    table.add_row("📈 Success Rate", bar)

    console.print(table)
    console.print()

    if success == total:
        console.print(
            Panel(
                "[bold green]✨ All paragraphs humanized successfully![/]",
                border_style="green",
                box=box.ROUNDED,
            )
        )
    elif fallback > 0:
        console.print(
            Panel(
                f"[bold yellow]⚠ {fallback} paragraph(s) fell back to original text.[/]\n"
                "[dim]Try increasing retries or passes for better coverage.[/]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )

    console.print(
        f"\n  [dim]Output saved to:[/] [bold bright_cyan]{os.path.abspath(output_path)}[/]\n"
    )


# ─── Utilities ────────────────────────────────────────────────────────────────

def _is_positive_float(value: str) -> bool:
    """Check if a string represents a positive float."""
    try:
        return float(value.strip()) > 0
    except (ValueError, AttributeError):
        return False


def _is_positive_int(value: str) -> bool:
    """Check if a string represents a positive integer."""
    try:
        val = int(value.strip())
        return val > 0
    except (ValueError, AttributeError):
        return False


def _abort() -> None:
    """Handle user cancellation gracefully."""
    console.print("\n  [dim red]✗ Pipeline cancelled by user.[/]\n")
    sys.exit(0)

