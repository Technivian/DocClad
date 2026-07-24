#!/usr/bin/env python3
"""Compare npm audit findings with a Git base revision.

The check deliberately scans every npm advisory, rather than lowering the
existing high-severity threshold. A finding that persists from the base
revision must have a matching, unexpired governed exception. New findings,
severity increases, and changes to a vulnerable dependency remain failures.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


WORKSPACES = ("client", "theme/static_src")
EXCEPTIONS_DIRECTORY = Path("docs/governance/decisions/exceptions/security")
SEVERITY_ORDER = {"info": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
APPROVAL_EVIDENCE_PATTERN = re.compile(
    r"https://github\.com/(?P<repository>[^/]+/[^/]+)/pull/(?P<number>\d+)$"
)
REQUIRED_EXCEPTION_FIELDS = (
    "status",
    "advisory_id",
    "workspace",
    "package",
    "affected_version",
    "reason_remediation_blocked",
    "risk",
    "safeguards",
    "owner",
    "approval_evidence",
    "expires_at",
    "remediation_reference",
    "exit_criteria",
    "exception_record",
)


@dataclass(frozen=True, order=True)
class Finding:
    workspace: str
    package: str
    advisory_id: str
    severity: str
    versions: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.workspace, self.package, self.advisory_id)


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def advisory_id(via: dict[str, Any]) -> str | None:
    url = via.get("url")
    if isinstance(url, str):
        match = re.search(r"/(GHSA-[a-z0-9-]+)$", url, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
    name = via.get("name")
    if isinstance(name, str) and name.upper().startswith("GHSA-"):
        return name.upper()
    return None


def audit_workspace(repository: Path, workspace: str) -> set[Finding]:
    completed = run(["npm", "--prefix", workspace, "audit", "--json"], cwd=repository)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"npm audit did not return JSON for {workspace}: {completed.stderr.strip()}"
        ) from exc

    lockfile = json.loads((repository / workspace / "package-lock.json").read_text())
    packages = lockfile.get("packages", {})
    findings: set[Finding] = set()
    for package, vulnerability in report.get("vulnerabilities", {}).items():
        if not isinstance(vulnerability, dict):
            continue
        severity = vulnerability.get("severity")
        if severity not in SEVERITY_ORDER:
            raise RuntimeError(f"Unknown npm severity for {workspace}/{package}: {severity!r}")
        versions = tuple(
            sorted(
                {
                    str(packages.get(node, {}).get("version"))
                    for node in vulnerability.get("nodes", [])
                    if packages.get(node, {}).get("version")
                }
            )
        )
        if not versions:
            raise RuntimeError(
                f"npm audit reported {workspace}/{package} without a resolved lockfile version"
            )
        for via in vulnerability.get("via", []):
            if not isinstance(via, dict):
                continue
            identifier = advisory_id(via)
            if identifier:
                findings.add(Finding(workspace, package, identifier, severity, versions))
    return findings


def audit_repository(repository: Path) -> set[Finding]:
    findings: set[Finding] = set()
    for workspace in WORKSPACES:
        if not (repository / workspace / "package-lock.json").is_file():
            raise RuntimeError(f"Missing lockfile for scanned workspace: {workspace}")
        findings.update(audit_workspace(repository, workspace))
    return findings


def parse_expiry(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("expires_at must be an ISO-8601 date (YYYY-MM-DD)") from exc


def github_api_json(url: str, token: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:  # nosec B310
            return json.loads(response.read())
    except (URLError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to verify GitHub approval evidence: {exc}") from exc


def validate_github_approval_evidence(
    evidence: list[str], github_repository: str, github_token: str
) -> None:
    for url in evidence:
        match = APPROVAL_EVIDENCE_PATTERN.fullmatch(url)
        if not match or match.group("repository").lower() != github_repository.lower():
            raise ValueError("Approval evidence must be a pull request in this repository")
        pull_url = (
            f"https://api.github.com/repos/{github_repository}/pulls/{match.group('number')}"
        )
        pull_request = github_api_json(pull_url, github_token)
        if not pull_request.get("merged_at"):
            raise ValueError(f"Approval evidence is not a merged pull request: {url}")
        reviews = github_api_json(f"{pull_url}/reviews", github_token)
        if not any(review.get("state") == "APPROVED" for review in reviews):
            raise ValueError(f"Approval evidence has no submitted approval: {url}")


def load_exceptions(
    repository: Path,
    today: dt.date,
    approval_verifier: Callable[[list[str]], None] | None = None,
) -> list[dict[str, Any]]:
    directory = repository / EXCEPTIONS_DIRECTORY
    if not directory.exists():
        return []

    exceptions: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir()):
        if path.name == "README.md":
            continue
        if path.suffix != ".json":
            raise ValueError(f"Unsupported security exception file: {path.relative_to(repository)}")
        try:
            exception = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path.relative_to(repository)}: {exc}") from exc
        if not isinstance(exception, dict):
            raise ValueError(f"Security exception must be a JSON object: {path.relative_to(repository)}")
        missing = [field for field in REQUIRED_EXCEPTION_FIELDS if not exception.get(field)]
        if missing:
            raise ValueError(f"Security exception {path.name} is missing: {', '.join(missing)}")
        if exception.get("status") != "approved":
            raise ValueError(f"Security exception {path.name} is not approved")
        if not isinstance(exception["safeguards"], list) or not exception["safeguards"]:
            raise ValueError(f"Security exception {path.name} needs one or more safeguards")
        evidence = exception["approval_evidence"]
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(url, str) and APPROVAL_EVIDENCE_PATTERN.fullmatch(url)
            for url in evidence
        ):
            raise ValueError(f"Security exception {path.name} needs GitHub pull-request approval evidence URLs")
        for field in ("remediation_reference", "exception_record"):
            if not isinstance(exception[field], str):
                raise ValueError(f"Security exception {path.name} has invalid {field}")
        if not isinstance(exception["remediation_reference"], str) or not exception["remediation_reference"].startswith("https://"):
            raise ValueError(f"Security exception {path.name} needs an HTTPS remediation_reference")
        record = repository / exception["exception_record"]
        if not exception["exception_record"].startswith("docs/governance/decisions/exceptions/") or not record.is_file():
            raise ValueError(f"Security exception {path.name} needs an existing governed exception_record")
        expiry = parse_expiry(exception["expires_at"])
        if expiry < today:
            raise ValueError(f"Security exception {path.name} expired on {expiry.isoformat()}")
        if approval_verifier:
            approval_verifier(evidence)
        exception["_path"] = str(path.relative_to(repository))
        exceptions.append(exception)
    return exceptions


def matching_exception(finding: Finding, exceptions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for exception in exceptions:
        if (
            exception["advisory_id"].upper() == finding.advisory_id
            and exception["workspace"] == finding.workspace
            and exception["package"] == finding.package
            and exception["affected_version"] in finding.versions
        ):
            return exception
    return None


def evaluate(
    base_findings: set[Finding], head_findings: set[Finding], exceptions: list[dict[str, Any]]
) -> list[str]:
    base_by_key = {finding.key: finding for finding in base_findings}
    failures: list[str] = []
    for finding in sorted(head_findings):
        base = base_by_key.get(finding.key)
        subject = f"{finding.workspace}: {finding.package} {finding.advisory_id}"
        if base is None:
            failures.append(f"new vulnerability: {subject} ({finding.severity})")
            continue
        if SEVERITY_ORDER[finding.severity] > SEVERITY_ORDER[base.severity]:
            failures.append(
                f"severity increased: {subject} ({base.severity} -> {finding.severity})"
            )
            continue
        if finding.versions != base.versions:
            failures.append(
                f"vulnerable dependency changed without resolving advisory: {subject} "
                f"({', '.join(base.versions)} -> {', '.join(finding.versions)})"
            )
            continue
        if matching_exception(finding, exceptions) is None:
            failures.append(f"continued baseline vulnerability without approved exception: {subject}")
    return failures


def base_worktree(repository: Path, ref: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="clmone-npm-audit-base-")
    path = Path(temporary.name) / "base"
    completed = run(["git", "worktree", "add", "--detach", str(path), ref], cwd=repository)
    if completed.returncode:
        temporary.cleanup()
        raise RuntimeError(f"Unable to materialize base ref {ref}: {completed.stderr.strip()}")
    return path, temporary


def remove_worktree(repository: Path, path: Path, temporary: tempfile.TemporaryDirectory[str]) -> None:
    run(["git", "worktree", "remove", "--force", str(path)], cwd=repository)
    temporary.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True, help="Git commit/ref to compare against")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument(
        "--verify-github-approvals",
        action="store_true",
        help="Require approval evidence to be a merged, approved PR in GITHUB_REPOSITORY.",
    )
    args = parser.parse_args()

    repository = args.repository.resolve()
    try:
        approval_verifier = None
        if args.verify_github_approvals:
            github_repository = os.environ.get("GITHUB_REPOSITORY")
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_repository or not github_token:
                raise ValueError(
                    "GITHUB_REPOSITORY and GITHUB_TOKEN are required to verify approval evidence"
                )
            approval_verifier = lambda evidence: validate_github_approval_evidence(
                evidence, github_repository, github_token
            )
        exceptions = load_exceptions(repository, args.today, approval_verifier)
        base, temporary = base_worktree(repository, args.base_ref)
        try:
            failures = evaluate(audit_repository(base), audit_repository(repository), exceptions)
        finally:
            remove_worktree(repository, base, temporary)
    except (RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"security baseline gate error: {exc}", file=sys.stderr)
        return 2

    if failures:
        print("npm audit baseline gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("npm audit baseline gate passed: no new, worsened, or unexcepted findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
