# claude-skills

A curated collection of security-audited Claude Code skills.

## Skills

| Skill | Version | Risk Score | Description |
|-------|---------|------------|-------------|
| [skill-security-auditor](./skill-security-auditor/) | 0.2.1 | self-exempt | Audits installed Claude skills for security risks across 7 dimensions |

## Security Policy

All skills in this repo are scanned weekly by `skill-security-auditor`.
Audit reports are stored in `skill-security-auditor/reports/`.

Skills with BLOCKED or CRITICAL ratings are removed or quarantined before publishing.

## Adding a Skill

1. Create a directory: `your-skill-name/`
2. Add `SKILL.md` with required frontmatter (`name`, `description`, `version`, `author`)
3. Open a PR — the weekly audit will run on merge
