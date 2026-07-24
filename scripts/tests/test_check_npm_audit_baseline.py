#!/usr/bin/env python3
"""Focused unit tests for the npm audit baseline comparison policy."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "check_npm_audit_baseline.py"
SPEC = importlib.util.spec_from_file_location("npm_audit_baseline", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def finding(advisory: str = "GHSA-r28c-9q8g-f849", severity: str = "high", version: str = "8.5.15"):
    return MODULE.Finding("client", "postcss", advisory.upper(), severity, (version,))


def exception(version: str = "8.5.15"):
    return {
        "advisory_id": "GHSA-R28C-9Q8G-F849",
        "workspace": "client",
        "package": "postcss",
        "affected_version": version,
    }


class EvaluateTests(unittest.TestCase):
    def test_new_finding_fails(self) -> None:
        failures = MODULE.evaluate(set(), {finding()}, [])
        self.assertEqual(len(failures), 1)
        self.assertIn("new vulnerability", failures[0])

    def test_persisting_finding_requires_exception(self) -> None:
        baseline = {finding()}
        failures = MODULE.evaluate(baseline, baseline, [])
        self.assertEqual(len(failures), 1)
        self.assertIn("without approved exception", failures[0])

    def test_matching_exception_allows_unchanged_baseline(self) -> None:
        baseline = {finding()}
        self.assertEqual(MODULE.evaluate(baseline, baseline, [exception()]), [])

    def test_severity_increase_cannot_be_excepted(self) -> None:
        failures = MODULE.evaluate({finding(severity="moderate")}, {finding()}, [exception()])
        self.assertEqual(len(failures), 1)
        self.assertIn("severity increased", failures[0])

    def test_vulnerable_dependency_change_cannot_be_excepted(self) -> None:
        failures = MODULE.evaluate({finding(version="8.5.15")}, {finding(version="8.5.16")}, [exception()])
        self.assertEqual(len(failures), 1)
        self.assertIn("changed without resolving", failures[0])


class ExceptionSchemaTests(unittest.TestCase):
    def write_exception(self, repository: Path, **overrides: object) -> None:
        record = repository / "docs/governance/decisions/exceptions/EXC-0001-postcss.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("# Temporary PostCSS exception\n")
        directory = record.parent / "security"
        directory.mkdir()
        payload = {
            "status": "approved",
            "advisory_id": "GHSA-r28c-9q8g-f849",
            "workspace": "client",
            "package": "postcss",
            "affected_version": "8.5.15",
            "reason_remediation_blocked": "A compatible patched release is unavailable.",
            "risk": "Source map disclosure.",
            "safeguards": ["Limit untrusted stylesheet processing."],
            "owner": "@security-owner",
            "approval_evidence": ["https://github.com/Technivian/CLMOne/pull/101"],
            "expires_at": "2026-08-01",
            "remediation_reference": "https://github.com/Technivian/CLMOne/issues/101",
            "exit_criteria": "Upgrade to a patched release and remove this record.",
            "exception_record": "docs/governance/decisions/exceptions/EXC-0001-postcss.md",
        }
        payload.update(overrides)
        (directory / "postcss.json").write_text(json.dumps(payload))

    def test_valid_exception_loads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_exception(repository)
            loaded = MODULE.load_exceptions(repository, date(2026, 7, 24))
        self.assertEqual(loaded[0]["package"], "postcss")

    def test_expired_exception_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_exception(repository, expires_at="2026-07-23")
            with self.assertRaisesRegex(ValueError, "expired"):
                MODULE.load_exceptions(repository, date(2026, 7, 24))

    def test_unapproved_exception_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_exception(repository, status="proposed")
            with self.assertRaisesRegex(ValueError, "not approved"):
                MODULE.load_exceptions(repository, date(2026, 7, 24))

    def test_github_evidence_must_be_merged_and_approved(self) -> None:
        evidence = ["https://github.com/Technivian/CLMOne/pull/101"]
        with patch.object(
            MODULE,
            "github_api_json",
            side_effect=[{"merged_at": "2026-07-23T12:00:00Z"}, [{"state": "APPROVED"}]],
        ):
            MODULE.validate_github_approval_evidence(evidence, "Technivian/CLMOne", "test-token")

        with patch.object(
            MODULE,
            "github_api_json",
            side_effect=[{"merged_at": "2026-07-23T12:00:00Z"}, [{"state": "COMMENTED"}]],
        ):
            with self.assertRaisesRegex(ValueError, "no submitted approval"):
                MODULE.validate_github_approval_evidence(
                    evidence, "Technivian/CLMOne", "test-token"
                )


if __name__ == "__main__":
    unittest.main()
