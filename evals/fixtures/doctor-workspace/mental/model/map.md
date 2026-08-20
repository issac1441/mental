---
id: system-map
kind: map
status: canonical
sources:
  - src-code
prerequisites: []
updated_at: 2026-08-10
---

# System map

[agreed] The router owns ticket intake, triage, and escalation.

Relationships:
- intake -> triage: every ticket is classified before assignment ([observed] src-code)
- triage -> [ghost-concept]: hard tickets consult the priority oracle
- triage -> escalation: SLA breach moves the ticket to a senior queue ([agreed])
