import anthropic
import json
import os
from tools import run_checkov, run_trivy, propose_patch, validate_patch, search_controls

from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
    {
        "name": "propose_patch",
        "description": (
            "Write a corrected version of a file to fix its security findings. "
            "Pass the ORIGINAL file path and the FULL corrected file content "
            "(the entire file, not a diff). When reviewing a directory, also pass "
            "root_path as the directory being remediated so patched files stay in a "
            "mirrored workspace tree. Returns the patched file path, patched root, and "
            "a unified diff. Call read_file first so you edit the real current content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
            "path": {"type": "string", "description": "Path of the file to fix"},
            "root_path": {"type": "string", "description": "Optional review root directory when patching multiple files in a folder"},
            "fixed_content": {"type": "string", "description": "The complete corrected file content"},
            },
            "required": ["path", "fixed_content"],
        },
    },
    {
        "name": "validate_patch",
        "description": "Validate a proposed patch by comparing the original and patched files or directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "original_path": {"type": "string", "description": "Path of the original file"},
                "patched_path": {"type": "string", "description": "Path of the patched file"},
            },
            "required": ["original_path", "patched_path"],
        },
    },
]

MAX_AGENT_TURNS = 15


def build_system_prompt(max_fix_attempts: int) -> str:
    return f"""You are a Kubernetes/IaC security reviewer.
Given a path, scan it with the available tools, then produce a prioritised report.
Rules:
- Run BOTH scanners and merge results; deduplicate findings that describe the same issue.
- Re-rank by REAL risk in context, not just the scanner's severity label.
- For each top finding: explain the risk in one sentence and give a concrete fix.
- Be concise. Group by severity.

After reporting findings, remediate the affected files and then validate the patch.
To remediate files:
1. Call read_file for each file you want to change.
2. Write corrected versions that resolve the top findings, changing as little else as possible.
3. Call propose_patch with the file path and the FULL corrected file. When the review target is a directory, pass root_path as that directory so all patched files land in the same mirrored patched workspace.
4. After all intended file edits for the attempt are staged, call validate_patch with the original review target and the patched file or patched root returned by propose_patch.
propose_patch writes to a separate copy or mirrored workspace, so you are never overwriting the user's files.
validate_patch will return the resolved and remaining issues, so you can confirm the patch worked.
If validate_patch reports remaining or new issues and attempts_left is above 0, read the patched files and try again.
When success is true, or attempts_left is 0, stop patching and give a final summary.
You have at most {max_fix_attempts} remediation attempts.
For each top finding, call search_controls with the finding text and cite the returned control id and title.
"""


def run_tool(name, inp):
    if name == "run_checkov":
        return run_checkov(inp["path"])
    if name == "run_trivy":
        return run_trivy(inp["path"])
    if name == "read_file":
        return {"content": open(inp["path"]).read()}
    if name == "propose_patch":
        return propose_patch(inp["path"], inp["fixed_content"], inp.get("root_path"))
    if name == "validate_patch":
        return validate_patch(inp["original_path"], inp["patched_path"])
    if name == "search_controls":
        return search_controls(inp["query"], inp.get("k", 3))

    return {"error": "unknown tool"}


def _final_text(blocks) -> str:
    return "".join(block.text for block in blocks if block.type == "text")


def review(path: str, max_fix_attempts: int = 3) -> str:
    if max_fix_attempts < 1:
        raise ValueError("max_fix_attempts must be at least 1")

    messages = [{"role": "user", "content": f"Please review the IaC at path: {path}"}]
    fix_attempts_used = 0
    patch_loop_closed = False

    for _ in range(MAX_AGENT_TURNS):
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20000,
            tools=tools,
            system=build_system_prompt(max_fix_attempts),
            messages=messages,
        )

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return _final_text(resp.content)

        control_messages = []
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue

            if patch_loop_closed and block.name in {"propose_patch", "validate_patch"}:
                result = {
                    "error": (
                        "Patch loop is closed. Do not attempt more remediation. "
                        "Provide the final summary instead."
                    ),
                    "attempts_used": fix_attempts_used,
                    "attempts_left": max(0, max_fix_attempts - fix_attempts_used),
                }
            else:
                result = run_tool(block.name, block.input)

            if block.name == "validate_patch" and "error" not in result:
                fix_attempts_used += 1
                success = not result["remaining"] and not result["new"]
                result["success"] = success
                result["attempts_used"] = fix_attempts_used
                result["attempts_left"] = max(0, max_fix_attempts - fix_attempts_used)

                if success:
                    patch_loop_closed = True
                    control_messages.append(
                        {
                            "type": "text",
                            "text": (
                                f"Patch validation succeeded on attempt {fix_attempts_used}. "
                                "Stop patching and provide the final summary."
                            ),
                        }
                    )
                elif result["attempts_left"] == 0:
                    patch_loop_closed = True
                    control_messages.append(
                        {
                            "type": "text",
                            "text": (
                                f"Patch validation still has remaining or new issues after "
                                f"{fix_attempts_used} attempts. Stop patching and provide the final summary."
                            ),
                        }
                    )
                else:
                    control_messages.append(
                        {
                            "type": "text",
                            "text": (
                                "Patch validation did not clear all issues. "
                                f"You may try again using the patched file as the new source. "
                                f"Attempts left: {result['attempts_left']}."
                            ),
                        }
                    )

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        messages.append({"role": "user", "content": results + control_messages})

    return (
        "Review stopped before completion because the agent exceeded the maximum number of "
        f"tool turns ({MAX_AGENT_TURNS})."
    )

        