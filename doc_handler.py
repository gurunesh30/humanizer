"""Document Handler module for reading and writing Word documents.

Provides utilities to read non-empty paragraphs from input .docx files
and append paraphrased output continuously/incrementally to prevent data loss.
"""

from pathlib import Path
from typing import Iterator, List, Optional
import docx
from docx import Document


class DocumentHandler:
    """Handles reading input documents and incrementally saving paraphrased output."""

    def __init__(self, input_path: Optional[str] = None, output_path: Optional[str] = None):
        """Initialize DocumentHandler with file paths.

        Args:
            input_path: Path to the source .docx document.
            output_path: Path to the target .docx document where output will be saved.
        """
        self.input_path = Path(input_path) if input_path else None
        self.output_path = Path(output_path) if output_path else None
        self._output_doc: Optional[docx.document.Document] = None

    def read_paragraphs(self, file_path: Optional[str] = None) -> List[str]:
        """Extract all non-empty paragraphs from a .docx file.

        Args:
            file_path: Optional override for the document path.

        Returns:
            List of non-blank paragraph text strings.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If no file path is provided or the file is not a .docx document.
        """
        target = Path(file_path) if file_path else self.input_path
        if not target:
            raise ValueError("No input file path specified.")
        if not target.exists():
            raise FileNotFoundError(f"Input file not found: {target}")
        if target.suffix.lower() != ".docx":
            raise ValueError(f"File must be a .docx document: {target}")

        doc = Document(str(target))
        paragraphs: List[str] = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                paragraphs.append(text)

        return paragraphs

    def iter_paragraphs(self, file_path: Optional[str] = None) -> Iterator[str]:
        """Yield non-empty paragraphs lazily from a .docx file.

        Args:
            file_path: Optional override for the document path.

        Yields:
            Non-blank paragraph text strings.
        """
        for paragraph in self.read_paragraphs(file_path):
            yield paragraph

    def init_output_document(self, output_path: Optional[str] = None) -> None:
        """Initialize or reset the output document handle.

        Ensures parent directories exist.

        Args:
            output_path: Optional override for output path.
        """
        if output_path:
            self.output_path = Path(output_path)
        if not self.output_path:
            raise ValueError("No output file path specified.")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_doc = Document()
        self._output_doc.save(str(self.output_path))

    def append_paragraph(self, text: str, output_path: Optional[str] = None) -> None:
        """Append a paragraph to the target .docx document and immediately persist to disk.

        This guarantees that even if the process terminates abruptly, all
        previously paraphrased paragraphs remain intact.

        Args:
            text: Paragraph text to append.
            output_path: Optional override for the target path.
        """
        if output_path:
            self.output_path = Path(output_path)
        if not self.output_path:
            raise ValueError("No output file path specified.")

        if self._output_doc is None:
            if self.output_path.exists():
                self._output_doc = Document(str(self.output_path))
            else:
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
                self._output_doc = Document()

        self._output_doc.add_paragraph(text)
        self._output_doc.save(str(self.output_path))
