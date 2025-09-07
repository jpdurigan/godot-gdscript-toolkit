import re
from types import MappingProxyType
from typing import List, Callable

from .types import Outcome, Node, FormattedLines
from .context import Context
from .constants import (
    INDENT_SIZE,
    DEFAULT_SURROUNDING_EMPTY_LINES_TABLE as DEFAULT_SURROUNDINGS_TABLE,
)


def format_block(
    statements: List[Node],
    statement_formatter: Callable,
    context: Context,
    surrounding_empty_lines_table: MappingProxyType = DEFAULT_SURROUNDINGS_TABLE,
) -> Outcome:
    previous_statement_name = None
    formatted_lines = []  # type: FormattedLines
    previously_processed_line_number = context.previously_processed_line_number
    for ix, statement in enumerate(statements):
        # Between-Statements gap handling: if any line in the gap is ignored,
        # preserve the entire gap verbatim; otherwise reconstruct blanks.
        if _has_ignored_in_range(
            previously_processed_line_number, statement.line, context
        ):
            formatted_lines += _verbatim_lines(
                previously_processed_line_number + 1, statement.line - 1, context
            )
        else:
            blank_lines = reconstruct_blank_lines_in_range(
                previously_processed_line_number, statement.line, context
            )
            if previous_statement_name is None:
                blank_lines = _remove_empty_strings_from_begin(blank_lines)
            else:
                blank_lines = _add_extra_blanks_due_to_previous_statement(
                    blank_lines,
                    previous_statement_name,  # type: ignore
                    surrounding_empty_lines_table,
                    context,
                )
                blank_lines = _add_extra_blanks_due_to_next_statement(
                    blank_lines,
                    statement.data,
                    surrounding_empty_lines_table,
                    context,
                )
            formatted_lines += blank_lines

        # Statement handling: if its span intersects ignored lines, emit verbatim.
        # Determine effective end as last non-empty/non-comment before next statement.
        if ix < len(statements) - 1:
            next_start_line = statements[ix + 1].line
        else:
            # Fallback to block dedent for last statement in this block.
            next_start_line = _find_dedent_line_number(statement.line, context)
        stmt_end = _effective_statement_end(statement.line, next_start_line, context)

        if _has_ignored_in_span(statement.line, stmt_end, context):
            formatted_lines += _verbatim_lines(statement.line, stmt_end, context)
            previously_processed_line_number = stmt_end
            previous_statement_name = statement.data
            continue

        lines, previously_processed_line_number = statement_formatter(
            statement, context
        )
        formatted_lines += lines
        previous_statement_name = statement.data
    dedent_line_number = _find_dedent_line_number(
        previously_processed_line_number, context
    )
    # Trailing gap to dedent: preserve verbatim if it includes ignored lines,
    # otherwise apply existing reconstruction and trimming rules.
    if _has_ignored_in_range(
        previously_processed_line_number, dedent_line_number, context
    ):
        formatted_lines += _verbatim_lines(
            previously_processed_line_number + 1, dedent_line_number - 1, context
        )
    else:
        lines_at_the_end = reconstruct_blank_lines_in_range(
            previously_processed_line_number, dedent_line_number, context
        )
        lines_at_the_end = _remove_empty_strings_from_end(lines_at_the_end)
        # Trim only trailing whitespace-only lines at end of inner blocks,
        # preserving interior indented blanks before comments/statements.
        if context.indent > 0:
            while len(lines_at_the_end) > 0 and lines_at_the_end[-1][1].strip() == "":
                lines_at_the_end.pop()
        formatted_lines += lines_at_the_end
    previously_processed_line_number = dedent_line_number - 1
    return (formatted_lines, previously_processed_line_number)


def _has_ignored_in_range(begin: int, end: int, context: Context) -> bool:
    # Check if any line in (begin, end) is ignored. Lines are 1-based.
    if end - begin <= 1:
        return False
    return any(context.ignore_mask[i] for i in range(begin + 1, end))


def _has_ignored_in_span(start_line: int, end_line: int, context: Context) -> bool:
    if end_line < start_line:
        return False
    return any(context.ignore_mask[i] for i in range(start_line, end_line + 1))


def _verbatim_lines(start_line: int, end_line: int, context: Context) -> FormattedLines:
    if start_line > end_line:
        return []
    return [
        (None, context.gdscript_code_lines[i]) for i in range(start_line, end_line + 1)
    ]


def _effective_statement_end(
    start_line: int, next_start_line: int, context: Context
) -> int:
    # Walk backwards from the line before next statement and find
    # the last non-empty, non-comment line to cap the statement span.
    end = max(start_line, next_start_line - 1)
    i = end
    while i >= start_line:
        line = context.gdscript_code_lines[i]
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            i -= 1
            continue
        break
    return i if i >= start_line else start_line


def reconstruct_blank_lines_in_range(
    begin: int, end: int, context: Context
) -> FormattedLines:
    comments_in_range = context.standalone_comments[begin + 1 : end]
    reconstructed_lines = []
    for line_no, comment in zip(range(begin + 1, end), comments_in_range):
        if comment is not None:
            prefix = (
                context.indent_string
                if not context.gdscript_code_lines[line_no].startswith("#")
                else ""
            )
            reconstructed_lines.append(prefix + comment)
        else:
            # Preserve indentation level for empty lines inside any indented block.
            # Keep global-scope separators empty.
            reconstructed_lines.append(
                context.indent_string if context.indent > 0 else ""
            )
    reconstructed_lines = _squeeze_lines(reconstructed_lines)
    return list(zip([None for _ in range(begin + 1, end)], reconstructed_lines))


# TODO: indent detection & refactoring
def _find_dedent_line_number(
    previously_processed_line_number: int, context: Context
) -> int:
    if (
        previously_processed_line_number == len(context.gdscript_code_lines) - 1
        or context.indent == 0
    ):
        return len(context.gdscript_code_lines)
    line_no = previously_processed_line_number + 1
    for line in context.gdscript_code_lines[previously_processed_line_number + 1 :]:
        if (
            line.startswith(" ")
            and re.search(r"^ {0,%d}[^ ]+" % (context.indent - 1), line) is not None
        ):
            break
        if (
            line.startswith("\t")
            and re.search(
                r"^\t{0,%d}[^\t]+" % ((context.indent / INDENT_SIZE) - 1), line
            )
            is not None
        ):
            break
        if (
            context.indent > 0
            and len(line) > 0
            and not line.startswith(" ")
            and not line.startswith("\t")
        ):
            break
        line_no += 1
    for line in context.gdscript_code_lines[line_no - 1 :: -1]:
        if line.strip() == "":
            line_no -= 1
        else:
            break
    return line_no


def _add_extra_blanks_due_to_previous_statement(
    blank_lines: FormattedLines,
    previous_statement_name: str,
    surrounding_empty_lines_table: MappingProxyType,
    context: Context,
) -> FormattedLines:
    # assumption: there is no sequence of empty lines longer than 1 (in blank lines)
    forced_blanks_num = surrounding_empty_lines_table.get(previous_statement_name)
    if forced_blanks_num is None:
        return blank_lines
    lines_to_prepend = forced_blanks_num
    has_leading_empty = len(blank_lines) > 0 and blank_lines[0][1].strip() == ""
    lines_to_prepend -= 1 if has_leading_empty else 0
    empty_line_content = context.indent_string if context.indent > 0 else ""
    empty_line = [(None, empty_line_content)]  # type: FormattedLines
    # If we're inside a block and the rule requires one blank after the
    # previous statement, convert the first existing empty separator to an
    # indented blank so class method separators are indented even if input had
    # an empty blank.
    if lines_to_prepend == 0 and has_leading_empty and context.indent > 0:
        blank_lines = [(None, empty_line_content)] + blank_lines[1:]
    return lines_to_prepend * empty_line + blank_lines


def _add_extra_blanks_due_to_next_statement(
    blank_lines: FormattedLines,
    next_statement_name: str,
    surrounding_empty_lines_table: MappingProxyType,
    context: Context,
) -> FormattedLines:
    # assumption: there is no sequence of empty lines longer than 2 (in blank lines)
    forced_blanks_num = surrounding_empty_lines_table.get(next_statement_name)
    if forced_blanks_num is None:
        return blank_lines
    first_empty_line_ix_from_end = _find_first_empty_line_ix_from_end(blank_lines)
    empty_lines_already_in_place = 1 if first_empty_line_ix_from_end > -1 else 0
    empty_lines_already_in_place += (
        1
        if first_empty_line_ix_from_end > 0
        and blank_lines[first_empty_line_ix_from_end - 1][1].strip() == ""
        else 0
    )
    lines_to_inject = forced_blanks_num
    lines_to_inject -= empty_lines_already_in_place
    # Insert separators; keep them indented inside blocks, empty at global scope.
    empty_line_content = context.indent_string if context.indent > 0 else ""
    empty_line = [(None, empty_line_content)]  # type: FormattedLines
    if first_empty_line_ix_from_end == -1:
        return lines_to_inject * empty_line + blank_lines
    return (
        blank_lines[:first_empty_line_ix_from_end]
        + lines_to_inject * empty_line
        + blank_lines[first_empty_line_ix_from_end:]
    )


def _find_first_empty_line_ix_from_end(blank_lines: FormattedLines) -> int:
    for line_no, (_, line) in reversed(list(enumerate(blank_lines))):
        if line.strip() == "":
            return line_no
    return -1


def _squeeze_lines(lines: List[str]) -> List[str]:
    # Treat any whitespace-only line as an empty separator and
    # collapse consecutive separators to a single one. This allows
    # keeping indentation on single blank lines inside blocks while
    # still squeezing multiple blank lines.
    squeezed_lines = []
    previous_was_empty = False
    for line in lines:
        is_empty = line.strip() == ""
        if not is_empty or not previous_was_empty:
            squeezed_lines.append(line)
        previous_was_empty = is_empty
    return squeezed_lines


def _remove_empty_strings_from_begin(lst: FormattedLines) -> FormattedLines:
    for i, (_, line) in enumerate(lst):
        if line.strip() != "":
            return lst[i:]
    return []


def _remove_empty_strings_from_end(lst: FormattedLines) -> FormattedLines:
    return list(reversed(_remove_empty_strings_from_begin(list(reversed(lst)))))
