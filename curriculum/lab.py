"""Offline curriculum answer key. Synthetic checks, never operational approval."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
for base in (ROOT, ROOT / "src", ROOT / "layer-b"):
    sys.path.insert(0, str(base))
CASES = []

def check(name, actual, expected):
    passed = actual == expected
    CASES.append({"case": name, "actual": actual, "expected": expected, "passed": passed})
    if not passed:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")

def rejects(name, call, error=ValueError):
    try:
        call()
    except error:
        check(name, error.__name__, error.__name__)
    else:
        raise AssertionError(f"{name}: expected {error.__name__}")

def sample(path):
    return json.loads((ROOT / path).read_text())



def run():
    from formal_topology.analysis import build_report
    from formal_topology.certificates import check_certificates
    policy = sample("examples/requirements.json")
    model = sample("examples/model.json")
    r = build_report(model,policy)
    check("reference obligations", r["status"], "OBLIGATIONS_HOLD")
    check("separate certificate checker", check_certificates(model,policy,r["property_results"])["certificates_valid"], True)
    loop = sample("examples/livelock.json")
    q = build_report(loop,policy)
    rows = {x["id"]:x for x in q["property_results"]}
    check("some execution completes", rows["completion-possible"]["status"], "PASS")
    check("not all executions complete", rows["completion-inevitable"]["status"], "FAIL")
    check("livelock has no deadlock", rows["no-deadlock"]["status"], "PASS")
    check("valid counterexample is not a passing property", check_certificates(loop,policy,q["property_results"])["certificates_valid"], True)
    check("no external execution authority", q["execution_authorized"], False)

if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["--verify"]):
        raise SystemExit("Usage: python curriculum/lab.py [--verify]")
    run()
    report = {"schema_version": 1, "status": "PASS", "case_count": len(CASES),
              "cases": CASES, "scope": "Synthetic curriculum checks only"}
    if sys.argv[1:] == ["--verify"]:
        expected = json.loads((Path(__file__).parent / "expected.json").read_text())
        if report != expected:
            raise AssertionError("Observed answers differ from curriculum/expected.json")
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
