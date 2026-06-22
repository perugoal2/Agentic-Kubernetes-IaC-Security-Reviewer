import json
import os, difflib, pathlib
import shutil
import subprocess
import sys
from pathlib import Path


def _checkov_command() -> list[str]:
    repo_root = Path(__file__).resolve().parent
    venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return [str(venv_python), "-m", "checkov.main"]

    if shutil.which("checkov"):
        return ["checkov"]

    return [sys.executable, "-m", "checkov.main"]


def _trivy_command() -> list[str]:
    trivy_path = shutil.which("trivy")
    if trivy_path:
        return [trivy_path]

    local_trivy = Path(__file__).resolve().parent / "bin" / "trivy.exe"
    if local_trivy.exists():
        return [str(local_trivy)]

    return ["trivy"]

def run_checkov(path: str) -> dict:
    """Run Checkov on the given path and return the results as a dictionary."""
    try:
        flag = "-d" if os.path.isdir(path) else "-f"
        proc = subprocess.run(
            [*_checkov_command(), flag, path, "-o", "json", "--compact", "--quiet"],
            capture_output=True,
            text=True,
        )

        if not proc.stdout.strip():
            return {
                "error": "Checkov execution failed.",
                "stderr": (proc.stderr or "").strip(),
                "returncode": proc.returncode,
            }

        data = json.loads(proc.stdout)

        blocks = data if isinstance(data, list) else [data]


        findings = []
        for blk in blocks:
            for chk in blk.get("results", {}).get("failed_checks", []):
                findings.append({
                    "id": chk.get("check_id"),
                    "name": chk.get("check_name"),
                    "resource": chk.get("resource"),
                    "severity": chk.get("severity") or "UNKNOWN",
                    "file": chk.get("file_path"),
                    "guideline": chk.get("guideline"),
                })
        return {"tool": "checkov", "count": len(findings), "findings": findings}
    
    except FileNotFoundError as exc:
        return {"error": f"Unable to locate Checkov executable: {exc}"}
    except json.JSONDecodeError as exc:
        return {
            "error": "Checkov returned invalid JSON.",
            "stdout": proc.stdout[:500] if "proc" in locals() else "",
            "details": str(exc),
        }

def run_trivy(path: str) -> dict:
    try:
        proc = subprocess.run(
            [*_trivy_command(), "config", "--format", "json", "--quiet", path],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return {"error": f"Unable to locate Trivy executable: {exc}"}

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "error": proc.stderr or "Trivy returned invalid JSON.",
            "returncode": proc.returncode,
        }
    findings = []
    for res in data.get("Results", []):
        for m in res.get("Misconfigurations", []):
            findings.append({
                "id": m.get("ID"), "name": m.get("Title"),
                "severity": m.get("Severity"), "file": res.get("Target"),
                "guideline": m.get("PrimaryURL"), "resource": m.get("CauseMetadata", {}).get("Resource"),
            })
    return {"tool": "trivy", "count": len(findings), "findings": findings}
    
PATCH_DIR = "patches"

def _patch_root_for(root_path: str | None, path: str) -> Path:
    base = Path(root_path or path).resolve()
    anchor = base if base.is_dir() else base.parent
    return Path(PATCH_DIR) / anchor.name


def _patched_target_path(path: str, root_path: str | None) -> Path:
    source = Path(path).resolve()
    patch_root = _patch_root_for(root_path, path)

    if root_path:
        base = Path(root_path).resolve()
        if base.is_dir():
            relative_path = source.relative_to(base)
            return patch_root / relative_path

    return patch_root / source.name


def propose_patch(path: str, fixed_content: str, root_path: str | None = None) -> dict:
    """Write a corrected copy of `path` (never touches the original).
    Returns the patched path, patched root, and a unified diff for display/validation."""
    original = pathlib.Path(path).read_text()
    patched_path = _patched_target_path(path, root_path)
    patched_path.parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(patched_path).write_text(fixed_content)

    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed_content.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{patched_path.as_posix()}",
    ))
    return {
        "patched_path": str(patched_path),
        "patched_root": str(_patch_root_for(root_path, path)),
        "diff": diff or "(no changes)",
    }

def validate_patch(original_path, patched_path):
    before = run_checkov(original_path)["findings"]
    after  = run_checkov(patched_path)["findings"]
    before_ids = {(f["id"], f["resource"]) for f in before}
    after_ids  = {(f["id"], f["resource"]) for f in after}
    return {
        "resolved": list(before_ids - after_ids),
        "remaining": list(after_ids),
        "new":       list(after_ids - before_ids),  # catch fixes that introduce issues
        "success": not after_ids,
    }

def search_controls(query: str, k: int = 3)-> dict:
    q = _model.encode([query]).tolist()
    res = _col.query(query_embeddings=q, n_results=k)
    return {"matches": [
        {"id": i, "title": m["title"], "text": d, "source": m["source"]}
        for i, d, m in zip(res["ids"][0], res["documents"][0], res["metadatas"][0])
    ]}