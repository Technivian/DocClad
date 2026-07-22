# CLM One Data, AI, and Intelligence

**Status:** Accepted  
**Purpose:** Define the governed data foundation and AI operating model.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Data Manager is foundational

CLM One must maintain one canonical registry for reusable data definitions.

Data Manager governs:

- property definitions;
- contract types;
- clause types;
- entity types;
- relationship types;
- obligation types;
- allowed values;
- ownership;
- usage;
- deprecation;
- migration;
- verification rules.

## 2. Property governance

Every Property Definition must include:

- stable ID;
- display name;
- technical name;
- description;
- data type;
- sensitivity;
- owner;
- allowed values;
- default;
- validation;
- search visibility;
- analytics visibility;
- integration mapping;
- AI extraction eligibility;
- deprecation status.

Near-duplicate properties must be prevented.

## 3. Data quality

The platform must track:

- completeness;
- verification status;
- conflicting values;
- stale data;
- invalid formats;
- orphaned references;
- duplicate entities;
- duplicate records.

## 4. Search

Search must support:

- contract names;
- counterparties;
- document text;
- canonical properties;
- clauses;
- dates;
- relationships;
- obligations;
- workflow state.

Search results must respect object-level access before result rendering.

## 5. AI capabilities

Allowed categories:

- metadata extraction;
- clause detection;
- classification;
- summarization;
- playbook comparison;
- suggested redlines;
- suggested fallback language;
- obligation extraction;
- renewal-date extraction;
- duplicate detection;
- natural-language search;
- portfolio explanation;
- drafting assistance.

## 6. AI suggestion model

Every AI Suggestion must record:

- use case;
- source documents;
- source locations;
- prompt or policy version;
- model;
- model version;
- timestamp;
- confidence;
- output;
- reviewer;
- disposition;
- final authoritative value if accepted;
- audit event.

## 7. Human verification

AI output remains non-authoritative until:

- accepted by an authorized user;
- auto-accepted under an approved low-risk policy;
- verified through deterministic rules;
- imported from an approved trusted source.

The UI must distinguish:

- extracted;
- suggested;
- verified;
- rejected;
- overridden.

## 8. AI playbooks

AI Playbooks combine:

- clause detection;
- preferred position;
- acceptable variants;
- fallback;
- prohibited language;
- risk;
- escalation;
- rationale;
- suggested action.

Playbooks are versioned and may be linked to contract type, workflow version, jurisdiction, counterparty category, or risk profile.

## 9. AI access control

AI must receive only context the requesting user is allowed to access.

The platform must enforce:

- workspace boundaries;
- record restrictions;
- ethical walls;
- privacy classifications;
- document-level access;
- field-level redaction where required.

## 10. AI governance

Workspace administrators must control:

- enabled use cases;
- approved providers;
- data residency;
- retention;
- model usage;
- human review;
- logging;
- cost limits;
- sensitive-data handling.

## 11. Analytics

Analytics should separate:

### Operational analytics

- queue volume;
- time to first action;
- cycle time;
- approval delay;
- review bottlenecks;
- SLA breaches;
- signature delay.

### Portfolio analytics

- contract value;
- renewal exposure;
- term distribution;
- governing law;
- risky clauses;
- obligation status;
- counterparty concentration.

### Governance analytics

- unverified AI fields;
- stale properties;
- policy exceptions;
- failed validations;
- permission anomalies;
- expiring exceptions;
- missing audit metadata.

## 12. Explainability

Any AI or rule-based recommendation affecting routing, risk, approval, or visibility must expose a human-readable explanation.
