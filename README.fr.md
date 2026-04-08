# claude-skills

**Language / 语言 / Idioma / Langue / Idioma / 言語**
[English](./README.md) · [中文](./README.zh.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Português](./README.pt.md) · [日本語](./README.ja.md)

---

> **Source canonique :** Ce dépôt — [github.com/WilliamHE-cyber/claude-skills](https://github.com/WilliamHE-cyber/claude-skills) — est la seule version officielle. Des forks et miroirs peuvent exister ; en cas de doute, référez-vous ici pour l'historique d'audit officiel. Copyright © WilliamHE-cyber.

Une collection organisée de skills Claude Code, auditées en matière de sécurité.
Chaque skill est analysée chaque semaine par le `skill-security-auditor` intégré avant publication.

---

## Skills

| Skill | Version | Score de Risque | Description |
|-------|---------|-----------------|-------------|
| [skill-security-auditor](./skill-security-auditor/) | 0.2.1 | auto-exempté | Audite les skills Claude sur 7 dimensions de risque avec capacité d'auto-amélioration |

---

## skill-security-auditor

> **Un auditeur de sécurité MVP pour les skills Claude Code — conçu pour découvrir ses propres angles morts et les corriger.**

### Le Problème

Les skills Claude Code sont des fichiers Markdown qui instruisent Claude d'exécuter des commandes shell, d'appeler des APIs externes, de lire et écrire des fichiers, et de gérer des identifiants. Une skill malveillante ou mal écrite pourrait exfiltrer des données, exécuter du code arbitraire ou divulguer silencieusement des clés API. Il n'existe actuellement aucune méthode standard pour évaluer le risque d'une skill avant de la charger.

### Ce que Fait Cette Skill

`skill-security-auditor` effectue une analyse statique de chaque skill dans `~/.claude/skills/`. Elle note chaque skill sur 7 dimensions de risque, produit des rapports structurés, maintient un journal d'audit en ajout seul, et — surtout — signale les lacunes dans sa propre logique de détection pour s'améliorer au fil du temps.

---

### Matrice de Notation de Risque à 7 Dimensions

Chaque dimension est notée de **0 à 10** et combinée en un score final de **0 à 100**.

| # | Dimension | Poids | Ce qu'elle détecte |
|---|-----------|-------|---------------------|
| D1 | **Exposition Réseau** | 20% | Appels HTTP externes, construction dynamique d'URLs, sockets bruts |
| D2 | **Accès aux Identifiants** | 20% | Clés API, tokens, fichiers `.env`, accès au trousseau |
| D3 | **Exécution de Code** | 18% | `subprocess`, `eval`, `exec`, `sudo`, pipe-to-shell |
| D4 | **Accès au Système de Fichiers** | 15% | Lecture/écriture hors workspace, accès à `~/.ssh`, `~/.aws` |
| D5 | **Exfiltration de Données** | 12% | Données de conversation transmises à l'extérieur, payloads Base64 |
| D6 | **Risque de Dépendances** | 8% | URLs `git+`, versions non épinglées, index non-PyPI |
| D7 | **Surface d'Injection de Prompts** | 7% | Contenu externe inséré dans les prompts sans assainissement |

**Niveaux de risque :**

| Score | Niveau | Action |
|-------|--------|--------|
| 0–19 | 🟢 FAIBLE | Aucune action requise |
| 20–39 | 🟡 MOYEN | Réviser dans 30 jours |
| 40–59 | 🟠 ÉLEVÉ | Réviser dans 7 jours |
| 60–79 | 🔴 CRITIQUE | Mise en quarantaine |
| 80–100 | ⛔ BLOQUÉ | Ne pas charger ; approbation humaine requise |

---

### Protocole de Vérification à Trois Couches

```
┌─────────────────────────────────────────────────────────┐
│  PRÉ-VÉRIFICATION       Avant de charger une skill       │
│  • Parser le frontmatter  • Consultation liste noire     │
│  • Scan des dépendances   • Vérification de provenance   │
├─────────────────────────────────────────────────────────┤
│  VÉRIFICATION RUNTIME     Pendant l'exécution            │
│  • Utilisation inattendue d'outils  • Accès identifiants │
│  • Réseau non documenté             • Patterns d'egress  │
├─────────────────────────────────────────────────────────┤
│  POST-VÉRIFICATION        Après l'audit                  │
│  • Détection de régression  • Révision faux positifs     │
│  • Calibration du scorer    • Génération du rapport      │
└─────────────────────────────────────────────────────────┘
```

---

### Boucle d'Auto-Amélioration

C'est le principe de conception central : **l'auditeur s'améliore grâce à son propre usage.**

Après chaque scan, `risk_scorer.py` émet des `self_notes` — des observations structurées sur la qualité de sa propre détection. Ces notes sont écrites dans le journal d'audit et présentées dans les rapports. Lors du prochain cycle d'itération, le scorer lit ses propres notes et propose des corrections concrètes — **en attendant la confirmation humaine** avant d'appliquer les changements.

```
scan → self_notes → proposition → confirmation humaine → patch → re-scan → vérification
```

**Historique des versions guidé par l'auto-découverte :**

| Version | Déclencheur | Correction |
|---------|------------|------------|
| v0.1.0 | Initial | Scanner statique à 7 dimensions |
| v0.2.0 | Self-note : hits D1 dans des blocs de code | Exclure les blocs ` ``` `; corriger faux positif D6 `>=`; reconstruire D7 |
| v0.2.1 | Analyse automatique de `cosmos-policy` | Pattern D2 `token` trop large — correspondait au vocabulaire ML ("tokenizer") |

---

### Utilisation

```bash
git clone https://github.com/WilliamHe-cyber/claude-skills.git
cp -r claude-skills/skill-security-auditor ~/.claude/skills/
```

```
/security-audit                      # Scanner toutes les skills
/security-audit langchain            # Scanner une skill
/security-audit --log                # Voir le résumé du journal
/security-audit --iterate            # Cycle d'auto-amélioration
/security-audit --pre nouvelle-skill # Pré-vérification avant installation
```

---

### Audits Hebdomadaires Automatisés

Ce dépôt exécute un agent Claude Code automatique chaque **lundi à 9h00** qui scanne toutes les skills, détecte les régressions, génère un rapport et — si des `self_notes` sont présentes — liste les améliorations proposées **en attendant confirmation humaine** avant de modifier tout code.

Les rapports d'audit sont publics et versionnés : [`skill-security-auditor/reports/`](./skill-security-auditor/reports/).

---

### Contribuer

1. **Ajouter une skill** — Créez `votre-skill/SKILL.md` et ouvrez une PR. Les skills notées CRITIQUE ou BLOQUÉE ne seront pas fusionnées.
2. **Améliorer le scanner** — Ouvrez une issue décrivant le faux positif ou la détection manquante.
3. **Notes de calibration** — Lors de l'ajustement des poids, ajoutez une entrée `## Calibration Note` dans `scoring_matrix.md`.

---

### Licence

MIT — voir [LICENSE](./LICENSE)

*Construit avec [Claude Code](https://claude.ai/claude-code) · Audité par lui-même · Auto-itération depuis v0.1.0*
