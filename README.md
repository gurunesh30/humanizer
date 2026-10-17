# ZeroGPT Word Document Paraphraser Pipeline

An automated, resilient Python pipeline that reads Microsoft Word documents (`.docx`), extracts non-empty paragraphs, paraphrases them sequentially via ZeroGPT using Playwright browser automation, and writes the output continuously into a new Word document.

---

## Features

- **Document Ingestion & Incremental Save:** Reads `.docx` files, automatically filters out empty lines/whitespace, and writes each paraphrased paragraph immediately to disk. If the process is halted or interrupted, all previously processed paragraphs are preserved.
- **Robust Multi-Selector Fallback Engine:** Features configurable primary and fallback selectors for input textareas, rewrite action buttons, and output containers to withstand UI updates.
- **Human-in-the-Loop Anti-Bot & CAPTCHA Pause:** Automatically detects Cloudflare verification challenges or Turnstile popups, notifies the user via CLI to solve the challenge in the open browser window, and resumes on `ENTER`.
- **Rate-Limit Mitigation & Retries:** Implements configurable delay spacing (default `4.0s`, configurable `3-5s`) between requests and an exponential backoff retry loop.
- **Zero Data Loss Fallback:** If a paragraph fails after maximum retries, the system gracefully falls back to appending the original paragraph to the target document.
- **Zero Paid APIs:** Built entirely using local Playwright browser automation with no external paid LLM APIs.

---

## Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd c:\dharshana\humanizer
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browser binaries:**
   ```bash
   playwright install chromium
   ```

---

## Usage

### 1. Generate a Sample Document (Optional)
To create a test Word document with non-empty paragraphs and whitespace:
```bash
python sample_generator.py
```
This generates `sample_input.docx`.

### 2. Run the Paraphrasing Pipeline
```bash
python main.py --input sample_input.docx --output paraphrased_output.docx
```

### 3. Command Line Options
```text
options:
  -h, --help            show this help message and exit
  -i, --input INPUT     Path to the input Microsoft Word document (.docx)
  -o, --output OUTPUT   Path where the paraphrased Microsoft Word document (.docx) will be saved
  --delay DELAY         Delay in seconds between consecutive paragraph submissions (default: 4.0)
  --retries RETRIES     Number of retry attempts per paragraph on failure (default: 3)
  --headless            Run browser in headless mode (default: False, recommended for CAPTCHAs)
  --url URL             Target ZeroGPT paraphraser endpoint URL
```

---

## Running Unit Tests

Run the configuration and document handler test suites:
```bash
python test_config.py
python test_doc_handler.py
```

---

## Project Structure

```text
humanizer/
├── main.py                 # Core CLI entry point and pipeline orchestrator
├── doc_handler.py          # Document reader and incremental persistence writer
├── zerogpt_automation.py   # Playwright automation engine and interaction logic
├── config.py               # Automation settings, selector fallbacks, and indicators
├── sample_generator.py     # Test document generator utility
├── test_config.py          # Unit tests for configuration
├── test_doc_handler.py     # Unit tests for document handling
├── requirements.txt        # Python dependency manifest
├── SYSTEM_SPECIFICATION.md # Architecture & system specification
└── README.md               # User documentation and guide
```
