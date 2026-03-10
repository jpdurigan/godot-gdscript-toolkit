import re
from typing import List, Optional
from dataclasses import dataclass

from lark import Tree


# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-positional-arguments
class Context:
    def __init__(
        self,
        previously_processed_line_number: int,
        single_indent_size: int,
        single_indent_string: str,
        max_line_length: int,
        gdscript_code_lines: List[str],
        standalone_comments: List[Optional[str]],
        inline_comments: List[Optional[str]],
        indent: int = 0,
    ):
        self.single_indent = single_indent_size
        self.single_indent_string = single_indent_string
        self.indent = indent
        self.indent_string = self.single_indent_string * (
            self.indent // self.single_indent
        )
        self.indent_regex = re.compile(f"^{self.single_indent_string[0]}+")
        self.previously_processed_line_number = previously_processed_line_number
        self.max_line_length = max_line_length
        self.gdscript_code_lines = gdscript_code_lines
        # Build ignore mask from standalone gdformat tags and null out comments
        # in ignored regions so postprocessing won't inject/move them.
        self.ignore_mask = _build_ignore_mask(self.gdscript_code_lines)
        self.standalone_comments = _null_comments_in_ignored_regions(
            standalone_comments, self.ignore_mask
        )
        self.inline_comments = _null_comments_in_ignored_regions(
            inline_comments, self.ignore_mask
        )
        self.annotations = []  # type: List[Tree]

    def create_child_context(self, previously_processed_line_number: int):
        return Context(
            single_indent_size=self.single_indent,
            single_indent_string=self.single_indent_string,
            previously_processed_line_number=previously_processed_line_number,
            max_line_length=self.max_line_length,
            gdscript_code_lines=self.gdscript_code_lines,
            standalone_comments=self.standalone_comments,
            inline_comments=self.inline_comments,
            indent=self.indent + self.single_indent,
        )


@dataclass
class ExpressionContext:
    prefix_string: str
    prefix_line: int  # earliest line number of prefix string
    suffix_string: str
    suffix_line: int  # earliest line number of suffix string


# Recognize tags only on standalone comment lines; forgiving spacing, case-insensitive.
_GDFORMAT_TAG_RE = re.compile(r"^\s*#\s*gdformat\s*:\s*(off|on)\b", re.IGNORECASE)


def _build_ignore_mask(lines: List[str]) -> List[bool]:
    # lines[0] is a synthetic empty line in this codebase's convention. Keep it False.
    ignore_mask = [False] * len(lines)
    in_ignore = False
    for i in range(1, len(lines)):
        line = lines[i]
        m = _GDFORMAT_TAG_RE.search(line)
        if m is None:
            ignore_mask[i] = in_ignore
            continue
        # Tag lines themselves are preserved verbatim as well
        ignore_mask[i] = True
        # Map tag value to boolean mask state
        in_ignore = m.group(1).lower() == "off"
    return ignore_mask


def _null_comments_in_ignored_regions(
    comments: List[Optional[str]], ignore_mask: List[bool]
) -> List[Optional[str]]:
    # Keep list shape; null out entries where ignore mask is active
    return [
        None if (i < len(ignore_mask) and ignore_mask[i]) else comment
        for i, comment in enumerate(comments)
    ]
