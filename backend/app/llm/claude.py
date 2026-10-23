"""Anthropic Claude models through the SDK's tool runner."""

from typing import Literal, TypedDict

import anthropic
from anthropic import beta_tool
from anthropic.lib.tools import ToolError

from .. import config
from .common import (CUT_OFF_NOTE, DECLINED, EMPTY_ANSWER, MAX_TOOL_ROUNDS, NEEDS_MORE_STEPS, LLMError, Reply, Toolbox,
                     closing_on_cancel, tool_error)

class MeasureArg(TypedDict):
    agg: Literal["sum", "count", "average", "min", "max", "distinct"]
    column: str


class GroupArg(TypedDict):
    column: str
    bucket: Literal["none", "day", "month", "quarter", "fy", "year"]


class FilterArg(TypedDict):
    column: str
    op: Literal["=", "!=", ">", ">=", "<", "<=", "between", "contains", "in", "blank", "not_blank"]
    value: str
    value2: str
    values: list[str]


# Models that accept the server-side refusal fallback (``fallbacks: "default"``).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


def chat(messages: list[dict], instructions: str, tools: Toolbox, emit=None, effort: str | None = None,
         transcript: list | None = None) -> Reply:
    """``transcript`` (from an earlier Reply) continues that exchange, tool calls and results included, with
    the last of ``messages`` as the new user message."""
    # Not streamed token by token: the toolbox reports each step, and the answer arrives whole.
    @beta_tool
    def analyse(table: str, measures: list[MeasureArg], group_by: list[GroupArg], filters: list[FilterArg],
                sort: Literal["value_desc", "value_asc", "label"], limit: int, across: bool) -> str:
        """Totals, counts, averages, lowest/highest values and breakdowns of one table, without SQL. Runs on exact decimals, returns the overall total, folds groups beyond the top N into an 'All others' row, and proves the groups add up to the total. Prefer it for every total, count, average or breakdown question.

        Args:
            table: Table name, e.g. ds2_sheet1.
            measures: 1-4 things to compute; for count, an empty column counts rows.
            group_by: 0-2 columns to break the figures down by; bucket groups a date column by day, month, quarter, fy (Indian financial year from April) or year, and is none for other columns.
            filters: Conditions every counted row must meet; between uses value and value2, in uses values; text matches ignore capitals; dates as YYYY-MM-DD; unused value fields are empty.
            sort: value_desc (largest first), value_asc, or label (alphabetical / date order).
            limit: Show only the top N groups (0 = all); the rest become one 'All others' row.
            across: true to spread the second group-by column across as columns (a pivot table) using the first measure.
        """
        try:
            return tools.analyse({"table": table, "measures": measures, "group_by": group_by, "filters": filters,
                                  "sort": sort, "limit": limit, "across": across})
        except Exception as exc:  # noqa: BLE001 - the real reason goes back to the model, which fixes its call
            raise ToolError(tool_error(exc)) from exc

    @beta_tool
    def run_sql(query: str) -> str:
        """Run one read-only DuckDB SELECT statement against the uploaded tables and return the result as JSON. Use it only for what analyse cannot do (joins, row-level lookups, calculations across columns of one row).

        Args:
            query: A single SELECT (or WITH ... SELECT) statement in DuckDB SQL.
        """
        try:
            return tools.run_sql(query)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(tool_error(exc)) from exc

    @beta_tool
    def calculate(expression: str) -> str:
        """Exact decimal arithmetic. Use it for every number you derive yourself (differences, totals of figures from different queries, percentages, averages) instead of calculating in your head.

        Args:
            expression: Arithmetic on plain numbers without thousands separators, e.g. (1192634 / 2593364) * 100. Allowed: + - * / brackets % round abs min max.
        """
        try:
            return tools.calculate(expression)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(tool_error(exc)) from exc

    @beta_tool
    def check_formula(table: str, target_column: str, expression: str, tolerance: float) -> str:
        """Test whether a column equals a formula of other columns on every row of a table. Returns how many rows match within the tolerance and examples of rows that do not. Use it to establish or verify how columns relate.

        Args:
            table: The table name, e.g. ds2_sheet1.
            target_column: The column the formula should reproduce, e.g. fine.
            expression: Formula over column names, e.g. net_wt * tunch / 100. Allowed: + - * / brackets % round abs min max; blank cells count as 0.
            tolerance: Largest difference still counted as a match, e.g. 0.001 for weights or 1 for rupee amounts.
        """
        try:
            return tools.check_formula(table, target_column, expression, tolerance)
        except Exception as exc:  # noqa: BLE001
            raise ToolError(tool_error(exc)) from exc

    options = {}
    if config.ANTHROPIC_MODEL in _FALLBACK_MODELS:
        # If a safety classifier declines, the API retries on a fallback model in the same call.
        options = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    conversation = [*transcript, {"role": "user", "content": messages[-1]["content"]}] if transcript else [
        {"role": m["role"], "content": m["content"]} for m in messages]
    client = anthropic.Anthropic()  # its own connection: closing it on cancel stops only this answer
    runner = client.beta.messages.tool_runner(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16000,
        system=instructions,
        tools=[analyse, run_sql, calculate, check_formula],
        output_config={"effort": effort or config.ANTHROPIC_EFFORT},
        max_iterations=MAX_TOOL_ROUNDS,
        messages=conversation,
        **options,
    )

    final = None
    history = list(conversation)
    try:
        with closing_on_cancel(tools.cancel, client.close):
            for message in runner:
                tools.check_cancelled()
                final = message
                history.append(message.to_param())
                # Kept for a correction round; the runner reuses these results, so each tool still runs once.
                results = runner.generate_tool_call_response() if message.stop_reason == "tool_use" else None
                if results:
                    history.append(results)
    except anthropic.AuthenticationError as exc:
        raise LLMError(502, "The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in backend/.env.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise LLMError(502, f"The Anthropic API key cannot use model {config.ANTHROPIC_MODEL}.") from exc
    except anthropic.NotFoundError as exc:
        raise LLMError(502, f"Model {config.ANTHROPIC_MODEL} was not found. Check ANTHROPIC_MODEL.") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError(429, "Anthropic is rate limiting requests. Try again in a minute.") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(502, f"Anthropic returned an error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError(502, "Could not reach Anthropic. Check the internet connection.") from exc

    if final is None:
        raise LLMError(502, "Anthropic returned no response.")

    answer = "\n\n".join(block.text for block in final.content if block.type == "text").strip()
    complete = bool(answer)
    if final.stop_reason == "refusal":
        answer, complete = DECLINED, False
    elif final.stop_reason == "tool_use":
        answer, complete = answer or NEEDS_MORE_STEPS, False
    elif final.stop_reason == "max_tokens":
        answer, complete = f"{answer}{CUT_OFF_NOTE}".strip(), False
    return Reply(answer or EMPTY_ANSWER, final.model, complete, history)
