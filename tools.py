import json
import os
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
    
if __name__ == "__main__":
    # result = run_checkov(
    #     str(Path(__file__).resolve().parent / "fixtures" / "bad.yaml")
    # )
    # print(json.dumps(result, indent=2))

    result = run_trivy(
        str(Path(__file__).resolve().parent / "fixtures" / "bad.yaml")
    )
    print(json.dumps(result, indent=2))

    