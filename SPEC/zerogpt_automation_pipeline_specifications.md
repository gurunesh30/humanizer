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
* **Logging & Retries:** Built-in `logging` and `tenacity` or custom retry loops with exponential backoff.
* **Interface:** Command Line Interface (CLI) via `argparse` or `click`.

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

### B. Web Automation & Resilience (`zerogpt_automation.py`)
1. **Target URL:** `https://www.zerogpt.com/paraphraser` (or active paraphraser endpoint).
2. **Selector Fallback Engine:** HTML structures on web tools change frequently. The automation layer must define primary and secondary CSS selectors for:
   * **Input Textarea:** `textarea#input-text`, `textarea[placeholder*='text']`, `textarea.paraphrase-input`
   * **Action Button:** `button:has-text('Paraphrase')`, `button:has-text('Rewrite')`, `button.btn-primary`
   * **Output Box:** `.output-text`, `#output-text`, `div.paraphrase-output`
3. **Anti-Bot & Cloudflare Handling:**
   * Run browser with `headless=False`.
   * On initial navigation, check if a Cloudflare challenge screen exists (`text="Verify you are human"` or Cloudflare iframe).
   * If detected, pause execution, prompt the user in the CLI to solve the CAPTCHA manually, and press `ENTER` to resume.
4. **Rate-Limit Mitigation:**
   * Add a configurable delay (default `3-5` seconds) between paragraph submissions.
   * Clear the input field completely before filling in new paragraph text (`textarea.fill('')`).

### C. Error Handling & State Recovery
1. If processing a single paragraph fails after $N$ retry attempts:
   * Log the error clearly.
   * Fall back to appending the **original paragraph** to the output document so the final document remains complete.
2. Provide real-time CLI progress output (e.g., `Processing paragraph 5/24...`).

---

## 5. File & Folder Structure

```
zerogpt-automation/
├── main.py                 # Core CLI application logic
├── doc_handler.py          # Document reading and continuous saving utilities
├── zerogpt_automation.py   # Playwright automation engine and selectors
├── requirements.txt        # Python dependencies
└── SYSTEM_SPECIFICATION.md # Architecture & system guidelines
```

---

## 6. Recommended `requirements.txt`

```text
python-docx>=0.8.11
playwright>=1.40.0
```

---

## 7. Execution Blueprint for Agent

When constructing this system, the agent must:
1. Generate `doc_handler.py` with incremental save support.
2. Generate `zerogpt_automation.py` with multi-selector fallback logic and human-in-the-loop CAPTCHA pauses.
3. Generate `main.py` offering a clean CLI interface (e.g., `python main.py --input paper.docx --output output.docx`).
4. Ensure no third-party paid APIs or external LLM libraries are included in the pipeline.