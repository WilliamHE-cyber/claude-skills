# Security Audit Report — {{DATE}}

**Auditor version:** {{SCORER_VERSION}}
**Scope:** {{SCOPE}}  <!-- "single: <skill>" or "batch: N skills" -->
**Triggered by:** {{TRIGGER}}  <!-- "manual" | "scheduled" | "pre-install" | "self-improvement" -->

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Skills scanned | {{TOTAL}} |
| BLOCKED | {{COUNT_BLOCKED}} |
| CRITICAL | {{COUNT_CRITICAL}} |
| HIGH | {{COUNT_HIGH}} |
| MEDIUM | {{COUNT_MEDIUM}} |
| LOW | {{COUNT_LOW}} |
| New regressions | {{REGRESSIONS}} |

{{#if BLOCKED_OR_CRITICAL}}
> **ACTION REQUIRED:** {{COUNT_BLOCKED_OR_CRITICAL}} skill(s) require immediate attention. See Section 2.
{{/if}}

---

## 1. Full Results

<!-- Sorted by score descending -->

| Skill | Score | Level | Top Risk |
|-------|-------|-------|----------|
{{RESULTS_TABLE}}

---

## 2. Critical / Blocked Skills

{{#each CRITICAL_BLOCKED_SKILLS}}
### {{name}}

- **Score:** {{score}}/100  [{{level}}]
- **Path:** `{{path}}`
- **Top dimensions:**
{{#each top_dims}}
  - {{dim}}: {{raw}}/10 ({{hits}} hits)
{{/each}}
- **Sample signals:**
{{#each sample_hits}}
  - L{{line}}: `{{snippet}}` — {{signal}}
{{/each}}
- **Recommended action:** {{action}}

{{/each}}

---

## 3. Regressions (Score Increased >10 pts)

{{#if regressions}}
| Skill | Previous Score | Current Score | Delta | Last Scanned |
|-------|---------------|--------------|-------|--------------|
{{REGRESSIONS_TABLE}}
{{else}}
No regressions detected.
{{/if}}

---

## 4. Scorer Self-Notes (Iteration Backlog)

These were generated automatically by `risk_scorer.py` and indicate potential
improvements to the scoring logic itself.

{{#if self_notes}}
| Skill | Note |
|-------|------|
{{SELF_NOTES_TABLE}}

**Next iteration tasks for scorer:**
{{ITERATION_TASKS}}
{{else}}
No self-notes this cycle.
{{/if}}

---

## 5. False-Positive Candidates

Skills where the scorer flagged signals but context suggests they are benign:

{{#if fp_candidates}}
| Skill | Dimension | Observation |
|-------|-----------|-------------|
{{FP_TABLE}}

**Action:** Review each manually. If confirmed benign, add an exemption comment
`<!-- audit:exempt D1 reason: documentation-only URL -->` in the SKILL.md.
{{else}}
None identified.
{{/if}}

---

## 6. Self-Improvement Actions Taken This Cycle

<!-- Populated by the SKILL.md post-check phase -->

{{IMPROVEMENT_ACTIONS}}

---

## Appendix — Scoring Matrix Version

Matrix: `scoring_matrix.md` v{{MATRIX_VERSION}}
Weights: D1=0.20, D2=0.20, D3=0.18, D4=0.15, D5=0.12, D6=0.08, D7=0.07

_Next scheduled audit: {{NEXT_AUDIT}}_
