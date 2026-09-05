"""Agent-in-the-loop harness: Claude drives a finos-mcp server through MCP.

For each task the model gets the server's tools (converted from ``tools/list``) plus a
synthetic ``read_resource`` tool so it can fetch and cite ``aigf://`` / ``cdm://`` /
``fdc3://`` resources.  A plain Messages-API tool loop is used deliberately: it has no
beta dependency, and every request and tool result is recorded for grading.

Deterministic grading (no LLM judge):
* every ``AIR-*`` id the answer cites must exist in the catalog (no hallucinated ids);
* at least one id from the task's ``must_cite`` list must appear;
* every tool in ``must_call`` must have been called;
* the model must not have refused.

An optional rubric grade via ``client.messages.parse`` runs when ``EVAL_JUDGE=1``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from mcp.client import Client
from pydantic import BaseModel, Field

AIR_ID = re.compile(r"\bAIR-(?:RC|OP|SEC|PREV|DET)-\d{3}\b")
DEFAULT_MODEL = "claude-opus-5"
MAX_TURNS = 10

SYSTEM_PROMPT = (
    "You are a governance analyst with read-only FINOS tools. Answer using the tools, "
    "never from memory. Every AIGF risk or control you mention must carry its AIR-* id, and "
    "you must cite the aigf:// resource URI you read for at least one of them (call "
    "read_resource on it). If a tool returns a structured error, follow its hint. "
    "Be concise: a short paragraph or a list, no preamble."
)


class Grade(BaseModel):
    relevance: int = Field(ge=1, le=5, description="Cited controls address the scenario")
    grounding: int = Field(ge=1, le=5, description="Claims are supported by tool results")
    rationale: str


@dataclass
class TaskRun:
    task_id: str
    prompt: str
    answer: str = ""
    tools_called: list[str] = field(default_factory=list)
    resources_read: list[str] = field(default_factory=list)
    cited: set[str] = field(default_factory=set)
    turns: int = 0
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_s: float = 0.0
    error: str | None = None
    grade: Grade | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "answer": self.answer,
            "tools_called": self.tools_called,
            "resources_read": self.resources_read,
            "cited": sorted(self.cited),
            "turns": self.turns,
            "stop_reason": self.stop_reason,
            "usage": {"input": self.input_tokens, "output": self.output_tokens},
            "duration_s": round(self.duration_s, 2),
            "error": self.error,
            "grade": self.grade.model_dump() if self.grade else None,
        }


def _tool_defs(tools: list[Any]) -> list[dict[str, Any]]:
    defs = [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.input_schema,
        }
        for t in tools
    ]
    defs.append(
        {
            "name": "read_resource",
            "description": "Read a resource by URI (e.g. aigf://control/AIR-PREV-020) to quote and cite it.",
            "input_schema": {
                "type": "object",
                "properties": {"uri": {"type": "string"}},
                "required": ["uri"],
                "additionalProperties": False,
            },
        }
    )
    return defs


async def _execute(mcp: Client, name: str, args: dict[str, Any], run: TaskRun) -> tuple[str, bool]:
    if name == "read_resource":
        uri = str(args.get("uri", ""))
        run.resources_read.append(uri)
        try:
            res = await mcp.read_resource(uri)
        except Exception as exc:
            return f"resource error: {exc}", True
        texts = [getattr(c, "text", "") for c in res.contents]
        return "\n".join(t for t in texts if t)[:20000], False
    run.tools_called.append(name)
    try:
        result = await mcp.call_tool(name, args)
    except Exception as exc:
        return f"tool error: {exc}", True
    if result.structured_content is not None and not result.is_error:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    else:
        text = "\n".join(getattr(c, "text", "") for c in result.content)
    return text[:60000], bool(result.is_error)


async def run_task(
    client: Any,
    mcp: Client,
    task: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    token_budget: int = 60000,
) -> TaskRun:
    run = TaskRun(task_id=task["id"], prompt=task["prompt"])
    tools = _tool_defs((await mcp.list_tools()).tools)
    messages: list[dict[str, Any]] = [{"role": "user", "content": task["prompt"]}]
    started = time.perf_counter()
    try:
        for _ in range(MAX_TURNS):
            run.turns += 1
            response = await client.messages.create(
                model=model,
                max_tokens=8000,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )
            run.input_tokens += response.usage.input_tokens
            run.output_tokens += response.usage.output_tokens
            run.stop_reason = response.stop_reason
            if response.stop_reason == "refusal":
                run.error = "refusal"
                break
            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                run.answer = "".join(b.text for b in response.content if b.type == "text")
                break
            results = []
            for block in tool_uses:
                text, is_error = await _execute(mcp, block.name, dict(block.input), run)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": text,
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "user", "content": results})
            if run.input_tokens + run.output_tokens > token_budget:
                run.error = "token_budget_exceeded"
                break
        else:
            run.error = "max_turns"
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"
    run.duration_s = time.perf_counter() - started
    run.cited = set(AIR_ID.findall(run.answer))
    return run


async def judge(
    client: Any, run: TaskRun, task: dict[str, Any], *, model: str = DEFAULT_MODEL
) -> Grade:
    response = await client.messages.parse(
        model=model,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": (
                    "Grade this answer to a FINOS AI governance question.\n\n"
                    f"Question: {task['prompt']}\n\nExpected ids (any of): {task.get('must_cite')}\n\n"
                    f"Answer:\n{run.answer}\n\nTools called: {run.tools_called}\n"
                    f"Resources read: {run.resources_read}"
                ),
            }
        ],
        output_format=Grade,
    )
    parsed = response.parsed_output
    assert isinstance(parsed, Grade)
    return parsed


def score(
    runs: list[TaskRun], tasks: dict[str, dict[str, Any]], known_ids: set[str]
) -> dict[str, Any]:
    n = len(runs)
    valid_ids = sum(1 for r in runs if r.cited and r.cited <= known_ids)
    must_cite = sum(1 for r in runs if r.cited & set(tasks[r.task_id].get("must_cite", [])))
    must_call = sum(
        1 for r in runs if set(tasks[r.task_id].get("must_call", [])) <= set(r.tools_called)
    )
    cited_resource = sum(1 for r in runs if r.resources_read)
    refusals = sum(1 for r in runs if r.error == "refusal")
    errors = sum(1 for r in runs if r.error and r.error != "refusal")
    graded = [r.grade for r in runs if r.grade]
    out: dict[str, Any] = {
        "tasks": n,
        "cited_valid_id_rate": round(valid_ids / n, 3) if n else 0.0,
        "must_cite_rate": round(must_cite / n, 3) if n else 0.0,
        "tool_correctness": round(must_call / n, 3) if n else 0.0,
        "resource_citation_rate": round(cited_resource / n, 3) if n else 0.0,
        "refusals": refusals,
        "errors": errors,
        "mean_turns": round(sum(r.turns for r in runs) / n, 2) if n else 0.0,
        "input_tokens": sum(r.input_tokens for r in runs),
        "output_tokens": sum(r.output_tokens for r in runs),
    }
    if graded:
        out["judge_relevance_mean"] = round(sum(g.relevance for g in graded) / len(graded), 2)
        out["judge_grounding_mean"] = round(sum(g.grounding for g in graded) / len(graded), 2)
    return out


async def run_suite(
    server: Any,
    tasks: list[dict[str, Any]],
    known_ids: set[str],
    *,
    model: str = DEFAULT_MODEL,
    use_judge: bool = False,
    concurrency: int = 3,
) -> tuple[list[TaskRun], dict[str, Any]]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    sem = asyncio.Semaphore(concurrency)
    async with Client(server, raise_exceptions=True) as mcp:

        async def one(task: dict[str, Any]) -> TaskRun:
            async with sem:
                run = await run_task(client, mcp, task, model=model)
                if use_judge and run.answer and not run.error:
                    try:
                        run.grade = await judge(client, run, task, model=model)
                    except Exception as exc:
                        run.error = f"judge: {exc}"
                return run

        runs = list(await asyncio.gather(*(one(t) for t in tasks)))
    by_id = {t["id"]: t for t in tasks}
    metrics = score(runs, by_id, known_ids)
    metrics["model"] = model
    return runs, metrics


def model_from_env() -> str:
    return os.environ.get("EVAL_MODEL", DEFAULT_MODEL)
