import anthropic
import json
import os
from tools import run_checkov, run_trivy

client = anthropic.Anthropic()

tools = [
    {
        "name": "run_checkov",
        "description": "Run Checkov on the given path and return the results as a dictionary.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "run_trivy",
        "description": "Run Trivy on the given path and return the results as a dictionary.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path and return it as a string.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
]

SYSTEM = """You are a Kubernetes/IaC security reviewer.
Given a path, scan it with the available tools, then produce a prioritised report.
Rules:
- Run BOTH scanners and merge results; deduplicate findings that describe the same issue.
- Re-rank by REAL risk in context, not just the scanner's severity label.
- For each top finding: explain the risk in one sentence and give a concrete fix.
- Be concise. Group by severity."""


def run_tool(name, inp):
    if name == "run_checkov":
        return run_checkov(inp["path"])
    elif name == "run_trivy":
        return run_trivy(inp["path"])
    elif name == "read_file":
        return {"content": open(inp["path"]).read()}
    return {"error": "unknown tool"}


def review(path: str) -> str:
    messages = [{"role": "user", "content": f"Please review the IaC at path: {path}"}]

    while True:
        resp= client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            tools=tools,
            system=SYSTEM,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
            break

        results = [
            {"type":"tool_result","tool_use_id":b.id,"content":json.dumps(run_tool(b.name,b.input))}
            for b in resp.content if b.type == "tool_use"
        ]

        messages.append({"role": "user", "content": results})