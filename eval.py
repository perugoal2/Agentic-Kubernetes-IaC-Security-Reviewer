import json
from tools import scan_findings, validate_patch


def _finding_ids(path: str) -> set[str]:
    return {finding["id"] for finding in scan_findings(path)}

def eval_detection(gt_path="fixtures/ground_truth.json"):
    gt = json.load(open(gt_path, encoding="utf-8"))
    tp = fp = fn = 0
    for f, expected in gt.items():
        found = _finding_ids(f)
        expected = set(expected)
        tp += len(found & expected)
        fp += len(found - expected)
        fn += len(expected - found)
    detection = tp / (tp + fn) if (tp + fn) else 0
    fp_rate   = fp / (tp + fp) if (tp + fp) else 0
    return {"detection_rate": round(detection, 3),
            "false_positive_rate": round(fp_rate, 3),
            "tp": tp, "fp": fp, "fn": fn}


def eval_remediation(gt_path="fixtures/ground_truth.json"):
    from agent import remediate

    gt = json.load(open(gt_path, encoding="utf-8"))
    attempted = clean = 0
    for f in gt:
        patched_path = remediate(f)
        if not patched_path:
            continue
        attempted += 1
        check = validate_patch(f, patched_path)
        if not check["remaining"] and not check["new"]:
            clean += 1
    validity = clean / attempted if attempted else 0
    return {"remediation_validity": round(validity, 3),
            "patched": attempted, "fully_resolved": clean}