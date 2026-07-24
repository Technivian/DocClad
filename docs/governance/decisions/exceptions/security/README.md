# Governed dependency-vulnerability exceptions

This directory is intentionally empty unless a temporary exception is
required. It is not an allowlist. The CI baseline gate parses only JSON files
in this directory and fails on an expired, incomplete, unapproved, or
unrecognised record.

Each exception must be accompanied by a normal `EXC-####-*.md` record in the
parent directory using the approved exception template. The JSON record is the
machine-readable companion and must contain all of the following:

- `status` set to `approved`;
- `advisory_id`, `workspace`, `package`, and the exact locked
  `affected_version`;
- the reason remediation is temporarily blocked, risk, and safeguards;
- a named owner;
- a same-repository GitHub pull-request URL supplying approval evidence;
- a hard `expires_at` date;
- a remediation issue or PR URL; and
- objective exit criteria; and
- `exception_record`, the path to its companion `EXC-####-*.md` record.

CI verifies that the evidence PR is merged and has a submitted GitHub approval;
a self-declared `approved` status or an arbitrary URL is not sufficient.

The exception is valid only for the exact advisory, workspace, package, and
locked version recorded. It cannot suppress a new advisory, a severity
increase, or a version change that leaves the advisory unresolved. Approval
evidence belongs on GitHub; do not recreate approval tables or timestamps in
the exception record.
