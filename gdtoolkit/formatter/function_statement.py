from functools import partial
from typing import Dict, Callable, Optional

from .context import Context, ExpressionContext
from .types import Outcome, Node, FormattedLines
from .expression import format_expression
from .block import format_block, reconstruct_blank_lines_in_range
from .statement_utils import format_simple_statement
from .var_statement import format_var_statement
from .expression_utils import is_any_comma
from .expression_to_str import expression_to_str


def format_func_statement(statement: Node, context: Context) -> Outcome:
    handlers = {
        "pass_stmt": partial(format_simple_statement, "pass"),
        "func_var_stmt": format_var_statement,
        "expr_stmt": _format_expr_statement,
        "return_stmt": _format_return_statement,
        "break_stmt": partial(format_simple_statement, "break"),
        "continue_stmt": partial(format_simple_statement, "continue"),
        "if_stmt": _format_if_statement,
        "while_stmt": partial(_format_branch, "while ", ":", 0),
        "for_stmt": _format_for_statement,
        "match_stmt": _format_match_statement,
        # fake statements:
        "match_branch": _format_match_branch,
    }  # type: Dict[str, Callable]
    return handlers[statement.data](statement, context)


def _format_expr_statement(statement: Node, context: Context) -> Outcome:
    expr = statement.children[0]
    expression_context = ExpressionContext("", statement.line, "")
    return format_expression(expr, expression_context, context)


def _format_return_statement(statement: Node, context: Context) -> Outcome:
    if len(statement.children) == 0:
        return format_simple_statement("return", statement, context)
    expr = statement.children[0]
    expression_context = ExpressionContext("return ", statement.line, "")
    return format_expression(expr, expression_context, context)


def _format_if_statement(statement: Node, context: Context) -> Outcome:
    formatted_lines = []  # type: FormattedLines
    previously_processed_line_number = None
    for branch in statement.children:
        if previously_processed_line_number is not None:
            blank_lines = reconstruct_blank_lines_in_range(
                previously_processed_line_number, branch.line, context
            )
            formatted_lines += blank_lines
        branch_prefix = {
            "if_branch": "if ",
            "elif_branch": "elif ",
            "else_branch": "else",
        }[branch.data]
        expr_position = {"if_branch": 0, "elif_branch": 0, "else_branch": None}[
            branch.data
        ]
        lines, previously_processed_line_number = _format_branch(
            branch_prefix, ":", expr_position, branch, context
        )
        formatted_lines += lines
    return (formatted_lines, previously_processed_line_number)  # type: ignore


def _format_for_statement(statement: Node, context: Context) -> Outcome:
    prefix = "for {} in ".format(statement.children[0].value)
    suffix = ":"
    expr_position = 1
    return _format_branch(prefix, suffix, expr_position, statement, context)


def _format_match_statement(statement: Node, context: Context) -> Outcome:
    prefix = "match "
    suffix = ":"
    expr_position = 0
    return _format_branch(prefix, suffix, expr_position, statement, context)


def _format_match_branch(
    statement: Node, context: Context
) -> Outcome:  # pylint: disable=too-many-locals
    # Special handling for long list-pattern branches: break with backslashes.
    try:
        pattern_wrapper = statement.children[0]
        # Some grammars produce an explicit 'pattern' wrapper, others inline it.
        # Support both: if first child is already a list, use it; otherwise dive one level.
        pattern = (
            pattern_wrapper
            if getattr(pattern_wrapper, "data", None) == "list_pattern"
            else pattern_wrapper.children[0]
        )
    except (
        AttributeError,
        IndexError,
    ):  # pragma: no cover - defensive: fallback to default path
        prefix = ""
        suffix = ":"
        expr_position = 0
        return _format_branch(prefix, suffix, expr_position, statement, context)

    # Only apply backslash wrapping to top-level list patterns in match branches
    if hasattr(pattern, "data") and getattr(pattern, "data", None) == "list_pattern":
        # Extract top-level elements (skip commas)
        elements = [child for child in pattern.children if not is_any_comma(child)]

        # Build candidate single-line header
        if len(elements) > 0:
            pattern_str = ", ".join(expression_to_str(e) for e in elements)
            single_line = f"{context.indent_string}{pattern_str}:"
            if len(single_line) <= context.max_line_length:
                # Fits in one line: use the default branch formatting
                prefix = ""
                suffix = ":"
                expr_position = 0
                return _format_branch(prefix, suffix, expr_position, statement, context)

            # If more than one element and it doesn't fit: one element per line with backslashes
            if len(elements) > 1:
                header_lines: FormattedLines = []
                for elem in elements[:-1]:
                    header_lines.append(
                        (
                            getattr(elem, "line", statement.line),
                            f"{context.indent_string}{expression_to_str(elem)}, \\",
                        )
                    )
                last_elem = elements[-1]
                header_lines.append(
                    (
                        getattr(last_elem, "line", statement.line),
                        f"{context.indent_string}{expression_to_str(last_elem)}:",
                    )
                )
                # Format the body with child context
                body_lines, last_processed_line_no = format_block(
                    statement.children[1:],
                    format_func_statement,
                    context.create_child_context(statement.end_line),
                )
                return (header_lines + body_lines, last_processed_line_no)

    # Fallback for non-list patterns or single long element: default behavior
    prefix = ""
    suffix = ":"
    expr_position = 0
    return _format_branch(prefix, suffix, expr_position, statement, context)


def _format_branch(
    prefix: str,
    suffix: str,
    expr_position: Optional[int],
    statement: Node,
    context: Context,
) -> Outcome:
    if expr_position is not None:
        expr = statement.children[expr_position]
        expression_context = ExpressionContext(prefix, statement.line, suffix)
        header_lines, last_processed_line_no = format_expression(
            expr, expression_context, context
        )
        offset = expr_position + 1
    else:
        header_lines = [
            (statement.line, "{}{}{}".format(context.indent_string, prefix, suffix))
        ]
        last_processed_line_no = statement.line
        offset = 0
    body_lines, last_processed_line_no = format_block(
        statement.children[offset:],
        format_func_statement,
        context.create_child_context(last_processed_line_no),
    )
    return (header_lines + body_lines, last_processed_line_no)
