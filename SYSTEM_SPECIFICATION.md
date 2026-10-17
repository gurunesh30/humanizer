# SYSTEM SPECIFICATION: ZeroGPT Word Document Paraphrasing Automation Pipeline

## 1. Project Overview & Objective
The goal is to build an automated Python-based pipeline that reads a Microsoft Word document (`.docx`), extracts text paragraph by paragraph, sends each paragraph through the ZeroGPT online Paraphrasing tool via browser automation (Playwright), collects the rephrased text, and writes the output sequentially into a new Word document.

---

## 2. Technical Stack & Environment

* **Language:** Python 3.9+
* **Browser Automation Engine:** Playwright (`playwright` Python library)
* **Browser Binary:** Playwright Chromium (`playwright install chromium`)
  * *Note:* No separate local browser installation (e.g., Brave or Chrome) is required. Playwright manages its own headless/headful Chromium binary.
* **Document I/O:** `python-docx`
* **Logging & Retries:** Built-in `logging` and exponential backoff retry loops.
* **Interface:** Command Line Interface (CLI) via `argparse`.

---

## 3. System Architecture & Workflow

```
[ Input Document (.docx) ]
           │
           ▼
1. Extract Non-Empty Paragraphs (doc_handler.py)
           │
           ▼
2. Initialize Playwright Browser Instance (zerogpt_automation.py)
   ├── Launch Chromium (headless=False)
   ├── Detect & Handle Cloudflare / CAPTCHA Pauses
   └── Loop Over Paragraphs:
       ├── Inject text into input textarea
       ├── Click Paraphrase / Rewrite button
       ├── Wait for output container mutation / completion
       └── Extract rephrased output string
           │
           ▼
3. Write Output to Target File Continuously (doc_handler.py)
           │
           ▼
[ Output Document (.docx) ]
```

---

## 4. Key Requirements & Implementation Details

### A. Document Handling (`doc_handler.py`)
1. Open the input file specified by the user.
2. Filter and yield non-blank paragraphs (ignore empty whitespace strings).
3. Append results incrementally to the target `.docx` file after every paragraph is processed to prevent data loss in case of script termination.
4. Preserve structural line breaks where appropriate.

### B. Web Automation & Resilience (`zerogpt_automation.py` & `config.py`)
1. **Target URL:** `https://www.zerogpt.com/paraphraser` (or active paraphraser endpoint).
2. **Selector Fallback Engine:** HTML structures on web tools change frequently. The automation layer defines primary and secondary CSS selectors for:
   * **Input Textarea:** `textarea#input-text`, `textarea[placeholder*='text']`, `textarea.paraphrase-input`, `textarea`
   * **Action Button:** `button:has-text('Paraphrase')`, `button:has-text('Rewrite')`, `button.btn-primary`
   * **Output Box:** `.output-text`, `#output-text`, `div.paraphrase-output`
3. **Anti-Bot & Cloudflare Handling:**
   * Run browser with `headless=False`.
   * On initial navigation and between requests, check if a Cloudflare challenge screen exists (`text="Verify you are human"` or Cloudflare Turnstile iframe).
   * If detected, pause execution, prompt the user in the CLI to solve the CAPTCHA manually, and press `ENTER` to resume.
4. **Rate-Limit Mitigation:**
   * Configurable delay (default `4.0` seconds, range `3-5` seconds) between paragraph submissions.
   * Clear the input field completely before filling in new paragraph text (`textarea.fill('')`).

### C. Error Handling & State Recovery
1. If processing a single paragraph fails after $N$ retry attempts:
   * Log the error clearly with exponential backoff.
   * Fall back to appending the **original paragraph** to the output document so the final document remains complete.
2. Provide real-time CLI progress output (e.g., `Processing paragraph 5/24...`).

---

## 5. File & Folder Structure

```
humanizer/
├── main.py                 # Core CLI application logic and orchestrator
├── doc_handler.py          # Document reading and continuous saving utilities
├── zerogpt_automation.py   # Playwright automation engine and interaction logic
├── config.py               # Automation configurations, selectors, and timeouts
├── sample_generator.py     # Utility to create test .docx documents
├── test_config.py          # Unit tests for configuration
├── test_doc_handler.py     # Unit tests for document reading and incremental saves
├── requirements.txt        # Python dependencies
├── README.md               # User manual and execution guide
└── SYSTEM_SPECIFICATION.md # Architecture & system guidelines
```

---

## 6. Execution Blueprint

1. `doc_handler.py` provides incremental save support to guarantee zero data loss.
2. `zerogpt_automation.py` provides multi-selector fallback logic and human-in-the-loop CAPTCHA pauses.
3. `main.py` offers a clean CLI interface (`python main.py --input paper.docx --output output.docx`).
4. Completely free of third-party paid APIs or external LLM dependencies.
