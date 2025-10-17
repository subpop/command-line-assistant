"""
Python-Markdown extensions that process a document and add ANSI color codes to
the output.

This module provides a set of extensions for python-markdown that render
markdown elements using ANSI escape codes suitable for terminal display.
"""

import re
from typing import Dict, List, Optional
from xml.etree import ElementTree as etree

import markdown
from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor

from command_line_assistant.rendering.colors import Style, colorize, stylize
from command_line_assistant.rendering.formatting import wrap
from command_line_assistant.rendering.theme import Theme

# Constants
MIN_TABLE_COLUMN_WIDTH = 3
TABLE_CELL_PADDING = 2
HORIZONTAL_RULE_LENGTH = 60
DEFAULT_LIST_INDEX = 1


class ANSIRenderer:
    """Base ANSI renderer that provides common formatting utilities."""

    def __init__(self, theme: Optional[Theme] = None):
        """Initialize the ANSI renderer with a theme.

        Args:
            theme: Theme instance to use for colors. If None, uses default theme.
        """
        self.theme = theme or Theme()

    def bold(self, text: str) -> str:
        """Format text as bold."""
        return stylize(text, Style.BOLD)

    def italic(self, text: str) -> str:
        """Format text as italic."""
        return stylize(text, Style.ITALIC)

    def underline(self, text: str) -> str:
        """Format text as underlined."""
        return stylize(text, Style.UNDERLINE)

    def strikethrough(self, text: str) -> str:
        """Format text as strikethrough."""
        return stylize(text, Style.STRIKETHROUGH)

    def code_inline(self, text: str) -> str:
        """Format inline code."""
        return colorize(text, self.theme.inline_code)

    def code_block(self, text: str, language: str = "") -> str:
        """Format code block."""
        lines = [
            colorize(line, self.theme.code_block_line)
            for line in text.rstrip().split("\n")
        ]
        longest_line_length = max(len(line) for line in text.rstrip().split("\n"))

        if language:
            lang_text = f" {language} snippet "
            padding = longest_line_length - len(lang_text) + 6
            # Color the border and language name separately
            header = (
                colorize("──", self.theme.code_block_border)
                + colorize(lang_text, self.theme.header)
                + colorize("─" * padding, self.theme.code_block_border)
            )
            footer_length = padding + len(lang_text) + 2
        else:
            padding = longest_line_length + 6
            header = colorize("─" * (padding + 2), self.theme.code_block_border)
            footer_length = padding + 2

        footer = colorize("─" * footer_length, self.theme.code_block_border)
        return f"\n{header}\n" + "\n".join(lines) + f"\n{footer}\n"

    def header(self, text: str, level: int) -> str:
        """Format header."""
        prefix = "#" * level
        return f"\n{colorize(f'{prefix} {text}', self.theme.header)}\n"

    def link(self, text: str, url: str, title: str = "") -> str:
        """Format link."""
        link_text = colorize(text, self.theme.link)
        if title:
            return f"{link_text} ({colorize(url, self.theme.link)}, {title})"
        return f"{link_text} ({colorize(url, self.theme.link)})"

    def image(self, alt_text: str, url: str, title: str = "") -> str:
        """Format image (as text representation)."""
        return f"[Image: {alt_text}] ({colorize(url, self.theme.image)})"

    def blockquote(self, text: str) -> str:
        """Format blockquote."""
        lines = text.strip().split("\n")
        quoted_lines = [f"│ {line}" for line in lines]
        return "\n".join(quoted_lines)

    def list_item(
        self, text: str, ordered: bool = False, index: int = DEFAULT_LIST_INDEX
    ) -> str:
        """Format list item."""
        marker = f"{index}." if ordered else "•"
        return f"{marker} {text}"

    def horizontal_rule(self) -> str:
        """Format horizontal rule."""
        return (
            f"\n{colorize('─' * HORIZONTAL_RULE_LENGTH, self.theme.horizontal_rule)}\n"
        )

    def format_table(self, rows: List[List[str]], header_row: bool = True) -> str:
        """Format a complete table with proper column alignment."""
        if not rows:
            return ""

        col_widths = self._calculate_column_widths(rows)
        result = []

        # Top border
        result.append(self._create_table_border(col_widths, "top"))

        # Process each row
        for row_idx, row in enumerate(rows):
            formatted_cells = self._format_table_cells(
                row, col_widths, row_idx, header_row
            )
            row_content = "│" + "│".join(formatted_cells) + "│"
            result.append(row_content)

            # Add separator after header
            if row_idx == 0 and header_row and len(rows) > 1:
                result.append(self._create_table_border(col_widths, "separator"))

        # Bottom border
        result.append(self._create_table_border(col_widths, "bottom"))

        return "\n" + "\n".join(result) + "\n"

    def _calculate_column_widths(self, rows: List[List[str]]) -> List[int]:
        """Calculate the width of each column in the table."""
        num_cols = len(rows[0])
        col_widths = []

        for col in range(num_cols):
            max_width = 0
            for row in rows:
                if col < len(row):
                    clean_text = self._strip_ansi(row[col])
                    max_width = max(max_width, len(clean_text))
            col_widths.append(
                max(MIN_TABLE_COLUMN_WIDTH, max_width + TABLE_CELL_PADDING)
            )

        return col_widths

    def _create_table_border(self, col_widths: List[int], border_type: str) -> str:
        """Create a table border line (top, separator, or bottom)."""
        border_chars = {
            "top": ("┌", "┬", "┐", "─"),
            "separator": ("├", "┼", "┤", "─"),
            "bottom": ("└", "┴", "┘", "─"),
        }

        left, middle, right, horizontal = border_chars[border_type]
        border = left
        for i, width in enumerate(col_widths):
            border += horizontal * width
            if i < len(col_widths) - 1:
                border += middle
        border += right
        return border

    def _format_table_cells(
        self, row: List[str], col_widths: List[int], row_idx: int, header_row: bool
    ) -> List[str]:
        """Format all cells in a table row."""
        formatted_cells = []
        for col, cell in enumerate(row):
            if col < len(col_widths):
                clean_text = self._strip_ansi(cell)
                padding = col_widths[col] - len(clean_text)
                left_pad = padding // 2
                right_pad = padding - left_pad

                if row_idx == 0 and header_row:
                    # Header cell
                    formatted_cell = f"{' ' * left_pad}{colorize(cell, self.theme.header)}{' ' * right_pad}"
                else:
                    # Regular cell
                    formatted_cell = f"{' ' * left_pad}{cell}{' ' * right_pad}"
                formatted_cells.append(formatted_cell)

        return formatted_cells

    def _strip_ansi(self, text: str) -> str:
        """Strip ANSI escape codes from text for width calculation."""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)


class FencedCodePreprocessor(Preprocessor):
    """Preprocessor that handles fenced code blocks before markdown splits text into blocks.

    This processor identifies fenced code blocks and stores them with unique markers,
    preventing markdown from processing the code content. The markers are later replaced
    by the tree processor.
    """

    # Pattern to match fenced code blocks (with optional leading whitespace)
    FENCED_BLOCK_RE = re.compile(
        r"^[ \t]*```(?P<lang>[\w#+.-]*)[^\n]*\n"  # Opening fence with optional language
        r"(?P<code>.*?)"  # Code content (non-greedy)
        r"^[ \t]*```\s*$",  # Closing fence
        re.MULTILINE | re.DOTALL,
    )

    def __init__(self, md: markdown.Markdown):
        """Initialize the preprocessor.

        Args:
            md: The Markdown instance
        """
        super().__init__(md)
        # Store code blocks for later retrieval
        # Using dynamic attribute assignment (type: ignore for mypy)
        if not hasattr(md, "_code_blocks"):
            md._code_blocks = {}  # type: ignore[attr-defined]
        self.code_blocks: Dict[str, Dict[str, str]] = md._code_blocks  # type: ignore[attr-defined]
        self.counter = 0

    def run(self, lines: List[str]) -> List[str]:
        """Process fenced code blocks in the text.

        Args:
            lines: List of text lines to process

        Returns:
            List of processed lines with code blocks replaced by markers
        """
        # Join lines into full text for regex matching
        text = "\n".join(lines)

        # Find and replace all fenced code blocks
        def replace_code_block(match):
            """Replace a matched code block with a marker."""
            lang = match.group("lang") or ""
            code = match.group("code")

            # Detect and remove base indentation from code
            code = self._dedent_code(code, match.group(0))

            # Generate unique marker
            marker_id = f"CODEBLOCK{self.counter}"
            self.counter += 1

            # Store code block data
            self.code_blocks[marker_id] = {"lang": lang, "code": code}

            # Return a placeholder that will become a <pre><code> element
            # Use a format that markdown will parse as HTML
            code_html = self._create_code_html(code, lang, marker_id)
            placeholder = self.md.htmlStash.store(code_html)
            return placeholder

        # Replace all fenced code blocks
        text = self.FENCED_BLOCK_RE.sub(replace_code_block, text)

        # Return as lines
        return text.split("\n")

    def _dedent_code(self, code: str, full_match: str) -> str:
        """Remove base indentation from code block content.

        Args:
            code: The code content
            full_match: The full matched text including fences

        Returns:
            Code with base indentation removed
        """
        # Find the indentation of the opening fence
        first_line = full_match.split("\n")[0]
        base_indent = len(first_line) - len(first_line.lstrip())

        if base_indent == 0:
            return code

        # Remove base indentation from each line
        lines = code.split("\n")
        dedented_lines = []
        for line in lines:
            if line.startswith(" " * base_indent):
                dedented_lines.append(line[base_indent:])
            elif line.startswith("\t" * base_indent):
                dedented_lines.append(line[base_indent:])
            elif line.strip() == "":
                # Preserve empty lines
                dedented_lines.append("")
            else:
                # Line has less indentation than base, keep as is
                dedented_lines.append(line.lstrip())

        return "\n".join(dedented_lines)

    def _create_code_html(self, code: str, language: str, marker_id: str) -> str:
        """Create a simple marker for the code block.

        Args:
            code: The code content
            language: The programming language (can be empty)
            marker_id: Unique marker ID for retrieval

        Returns:
            Marker string that will be replaced by postprocessor
        """
        # Return a simple marker that the postprocessor will replace
        return f"<!--{marker_id}-->"


class CodeBlockPostprocessor(Postprocessor):
    """Postprocessor that replaces code block markers with ANSI formatted code."""

    def __init__(self, md: markdown.Markdown, renderer: ANSIRenderer):
        """Initialize the postprocessor.

        Args:
            md: The Markdown instance
            renderer: ANSI renderer for formatting code blocks
        """
        super().__init__(md)
        self.renderer = renderer
        self.code_blocks = getattr(md, "_code_blocks", {})

    def run(self, text: str) -> str:
        """Replace code block markers with ANSI formatted code.

        Args:
            text: The processed markdown text

        Returns:
            Text with code blocks rendered as ANSI
        """
        # Replace each marker with formatted code
        for marker_id, block_data in self.code_blocks.items():
            marker = f"<!--{marker_id}-->"
            if marker in text:
                code = block_data["code"]
                lang = block_data["lang"]
                formatted = self.renderer.code_block(code, lang)
                text = text.replace(marker, formatted)

        return text


class ANSITreeProcessor(Treeprocessor):
    """Tree processor that converts HTML elements to ANSI formatted text."""

    def __init__(self, md: markdown.Markdown, renderer: ANSIRenderer):
        super().__init__(md)
        self.renderer = renderer
        self.parent_map: Dict[etree.Element, etree.Element] = {}
        self.list_counters: Dict[etree.Element, int] = {}
        self._setup_tag_formatters()

    def _setup_tag_formatters(self):
        """Set up tag formatting dispatch table."""
        self._tag_formatters = {
            # Text formatting
            "strong": self._format_bold,
            "b": self._format_bold,
            "em": self._format_italic,
            "i": self._format_italic,
            "u": self._format_underline,
            "del": self._format_strikethrough,
            "s": self._format_strikethrough,
            "code": self._format_code,
            # Block elements
            "pre": self._format_pre,
            "blockquote": self._format_blockquote,
            "hr": self._format_hr,
            "p": self._format_paragraph,
            # Links and media
            "a": self._format_link,
            "img": self._format_image,
            # Lists
            "li": self._format_list_item,
            "ul": self._format_list_container,
            "ol": self._format_list_container,
            # Tables
            "table": self._format_table,
            "thead": self._format_table_element,
            "tbody": self._format_table_element,
            "td": self._format_table_element,
            "th": self._format_table_element,
            "tr": self._format_table_row,
            # Other
            "br": self._format_br,
        }

    def run(self, root: etree.Element) -> None:
        """Process the element tree and convert to ANSI text."""
        # First pass: set up parent relationships
        self._set_parent_relationships(root)

        text = self._process_element(root)
        # Replace the root with a single text node
        root.clear()
        root.text = text
        root.tag = "div"  # Use a neutral container

    def _set_parent_relationships(
        self, elem: etree.Element, parent: Optional[etree.Element] = None
    ) -> None:
        """Set parent relationships for all elements."""
        if parent is not None:
            self.parent_map[elem] = parent
        for child in elem:
            self._set_parent_relationships(child, elem)

    def _process_element(self, elem: etree.Element) -> str:
        """Process a single element and its children."""
        tag = elem.tag.lower()
        text = elem.text or ""
        tail = elem.tail or ""

        # Process children first
        child_text = ""
        for child in elem:
            child_text += self._process_element(child)

        # Combine text content
        content = text + child_text

        # Apply formatting based on tag
        formatted = self._format_by_tag(tag, elem, content)

        return formatted + tail

    def _format_by_tag(self, tag: str, elem: etree.Element, content: str) -> str:
        """Format content based on HTML tag."""
        # Check for headers first (h1-h6)
        if self._is_header_tag(tag):
            level = int(tag[1])
            return self.renderer.header(wrap(content), level)

        # Use dispatch table for known tags
        formatter = self._tag_formatters.get(tag)
        if formatter:
            return formatter(elem, content)

        # Default: return wrapped content
        return wrap(content)

    # Text formatting methods
    def _format_bold(self, elem: etree.Element, content: str) -> str:
        return self.renderer.bold(wrap(content))

    def _format_italic(self, elem: etree.Element, content: str) -> str:
        return self.renderer.italic(wrap(content))

    def _format_underline(self, elem: etree.Element, content: str) -> str:
        return self.renderer.underline(wrap(content))

    def _format_strikethrough(self, elem: etree.Element, content: str) -> str:
        return self.renderer.strikethrough(wrap(content))

    def _format_code(self, elem: etree.Element, content: str) -> str:
        """Format code - inline or block depending on parent."""
        parent = self.parent_map.get(elem)
        if parent is not None and parent.tag.lower() == "pre":
            return content  # Handled by <pre> case
        return self.renderer.code_inline(content)

    # Block element methods
    def _format_pre(self, elem: etree.Element, content: str) -> str:
        return self._format_code_block(elem, wrap(content))

    def _format_blockquote(self, elem: etree.Element, content: str) -> str:
        return self.renderer.blockquote(wrap(content))

    def _format_hr(self, elem: etree.Element, content: str) -> str:
        return self.renderer.horizontal_rule()

    def _format_paragraph(self, elem: etree.Element, content: str) -> str:
        return f"{wrap(content)}\n" if content.strip() else ""

    # List methods
    def _format_list_container(self, elem: etree.Element, content: str) -> str:
        return wrap(content)

    def _format_list_item(self, elem: etree.Element, content: str) -> str:
        """Format list item element, determining if it's ordered or unordered."""
        parent = self.parent_map.get(elem)
        if parent is None:
            return self.renderer.list_item(wrap(content), ordered=False)

        parent_tag = parent.tag.lower()
        if parent_tag == "ol":
            # Ordered list - track the index
            if parent not in self.list_counters:
                self.list_counters[parent] = 0
            self.list_counters[parent] += 1
            index = self.list_counters[parent]
            return self.renderer.list_item(wrap(content), ordered=True, index=index)

        # Unordered list or unknown parent
        return self.renderer.list_item(wrap(content), ordered=False)

    # Table methods
    def _format_table_element(self, elem: etree.Element, content: str) -> str:
        return wrap(content)

    def _format_table_row(self, elem: etree.Element, content: str) -> str:
        return wrap(content)

    # Link and media methods
    def _format_link(self, elem: etree.Element, content: str) -> str:
        """Format link element."""
        url = elem.get("href", "")
        title = elem.get("title", "")
        return self.renderer.link(wrap(content), url, title)

    def _format_image(self, elem: etree.Element, content: str) -> str:
        """Format image element."""
        alt = elem.get("alt", "")
        src = elem.get("src", "")
        title = elem.get("title", "")
        return self.renderer.image(alt, src, title)

    # Other methods
    def _format_br(self, elem: etree.Element, content: str) -> str:
        return "\n"

    def _is_header_tag(self, tag: str) -> bool:
        """Check if tag is a header tag (h1-h6)."""
        return tag.startswith("h") and len(tag) == 2 and tag[1].isdigit()

    def _format_code_block(self, elem: etree.Element, content: str) -> str:
        """Format code block element."""
        code_elem = elem.find("code")
        if code_elem is not None:
            language = code_elem.get("class", "").replace("language-", "")
            # Get the text content - ElementTree automatically unescapes HTML entities
            code_text = code_elem.text or ""
            return self.renderer.code_block(code_text, language)
        else:
            return self.renderer.code_block(content)

    def _format_table(self, elem: etree.Element, content: str) -> str:
        """Format entire table element with proper column alignment."""
        rows = []
        has_header = False

        # Process all rows in the table
        for row_elem in elem.findall(".//tr"):
            cells = []
            row_has_th = False

            # Get all cells in this row
            for cell_elem in row_elem.findall(".//td") + row_elem.findall(".//th"):
                cell_content = self._process_element(cell_elem)
                # Clean up cell content - remove extra whitespace and newlines
                cell_content = cell_content.strip().replace("\n", " ")
                cells.append(cell_content)
                if cell_elem.tag.lower() == "th":
                    row_has_th = True

            if cells:  # Only add non-empty rows
                rows.append(cells)
                if row_has_th:
                    has_header = True

        if not rows:
            return ""

        return self.renderer.format_table(rows, header_row=has_header)


class ANSIExtension(Extension):
    """Main Python-Markdown extension that provides ANSI terminal output."""

    def __init__(self, theme: Optional[Theme] = None, **kwargs):
        self.config = {
            "renderer": [ANSIRenderer(theme), "ANSI renderer instance"],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        """Register the ANSI processors."""
        renderer = self.getConfig("renderer")

        # Register our fenced code preprocessor
        # This runs before markdown splits text into blocks
        fenced_preprocessor = FencedCodePreprocessor(md)
        md.preprocessors.register(fenced_preprocessor, "fenced_code_block", 25)

        # Register the tree processor to convert HTML to ANSI
        tree_processor = ANSITreeProcessor(md, renderer)
        md.treeprocessors.register(tree_processor, "ansi", 0)

        # Register the postprocessor to replace code block markers with ANSI
        # This runs after the tree processor
        code_postprocessor = CodeBlockPostprocessor(md, renderer)
        md.postprocessors.register(code_postprocessor, "code_blocks", 15)


# Convenience functions
def markdown_to_ansi(text: str, theme: Optional[Theme] = None, **kwargs) -> str:
    """Convert markdown text to ANSI formatted text.

    Args:
        text: Markdown text to convert
        theme: Theme instance to use for colors. If None, uses default theme.
        **kwargs: Additional arguments passed to markdown.markdown()

    Returns:
        ANSI formatted text suitable for terminal display
    """

    md = ANSIMarkdown(theme=theme, **kwargs)
    return md.convert(text)


class ANSIMarkdown(markdown.Markdown):
    """Markdown processor that converts markdown to ANSI formatted text. This
    is a convenience class that can be used in place of a markdown.Markdown
    instance to render markdown to ANSI formatted text suitable for terminal
    display."""

    def __init__(self, theme: Optional[Theme] = None, **kwargs):
        super().__init__(extensions=[ANSIExtension(theme), "tables"], **kwargs)
