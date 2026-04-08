# claude-skills

**Language / 语言 / Idioma / Langue / Idioma / 言語**
[English](./README.md) · [中文](./README.zh.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Português](./README.pt.md) · [日本語](./README.ja.md)

---

> **Fonte canônica:** Este repositório — [github.com/WilliamHE-cyber/claude-skills](https://github.com/WilliamHE-cyber/claude-skills) — é a única versão oficial. Forks e espelhos podem existir; em caso de dúvida, consulte aqui o histórico de auditoria autoritativo. Copyright © WilliamHE-cyber.

Uma coleção curada de skills para Claude Code, auditadas em segurança.
Cada skill é verificada semanalmente pelo `skill-security-auditor` integrado antes de ser publicada.

---

## Skills

| Skill | Versão | Pontuação de Risco | Descrição |
|-------|--------|-------------------|-----------|
| [skill-security-auditor](./skill-security-auditor/) | 0.2.1 | auto-isento | Audita skills do Claude em 7 dimensões de risco com capacidade de auto-melhoria |

---

## skill-security-auditor

> **Um auditor de segurança MVP para skills do Claude Code — projetado para descobrir seus próprios pontos cegos e corrigi-los.**

### O Problema

As skills do Claude Code são arquivos Markdown que instruem o Claude a executar comandos shell, chamar APIs externas, ler e escrever arquivos e gerenciar credenciais. Uma skill maliciosa ou mal escrita pode exfiltrar dados, executar código arbitrário ou vazar chaves de API silenciosamente. Atualmente não existe um método padrão para avaliar o risco de uma skill antes de carregá-la.

### O que Esta Skill Faz

`skill-security-auditor` realiza análise estática em cada skill no diretório `~/.claude/skills/`. Pontua cada skill em 7 dimensões de risco, produz relatórios estruturados, mantém um log de auditoria somente-adição e — crucialmente — sinaliza lacunas em sua própria lógica de detecção para melhorar ao longo do tempo.

---

### Matriz de Pontuação de Risco em 7 Dimensões

Cada dimensão é pontuada de **0 a 10** e combinada em uma pontuação final de **0 a 100**.

| # | Dimensão | Peso | O que Detecta |
|---|----------|------|---------------|
| D1 | **Exposição de Rede** | 20% | Chamadas HTTP externas, construção dinâmica de URLs, sockets brutos |
| D2 | **Acesso a Credenciais** | 20% | Chaves de API, tokens, arquivos `.env`, acesso ao chaveiro |
| D3 | **Execução de Código** | 18% | `subprocess`, `eval`, `exec`, `sudo`, pipe-to-shell |
| D4 | **Acesso ao Sistema de Arquivos** | 15% | Leitura/escrita fora do workspace, acesso a `~/.ssh`, `~/.aws` |
| D5 | **Exfiltração de Dados** | 12% | Dados de conversa transmitidos externamente, payloads Base64 |
| D6 | **Risco de Dependências** | 8% | URLs `git+`, versões não fixadas, índices não-PyPI |
| D7 | **Superfície de Injeção de Prompts** | 7% | Conteúdo externo inserido em prompts sem sanitização |

**Níveis de risco:**

| Pontuação | Nível | Ação |
|-----------|-------|------|
| 0–19 | 🟢 BAIXO | Nenhuma ação necessária |
| 20–39 | 🟡 MÉDIO | Revisar em 30 dias |
| 40–59 | 🟠 ALTO | Revisar em 7 dias |
| 60–79 | 🔴 CRÍTICO | Quarentena pendente de revisão |
| 80–100 | ⛔ BLOQUEADO | Não carregar; requer aprovação humana |

---

### Protocolo de Verificação em Três Camadas

```
┌─────────────────────────────────────────────────────────┐
│  PRÉ-VERIFICAÇÃO        Antes de carregar uma skill      │
│  • Parsear frontmatter  • Consulta de lista negra        │
│  • Scan de dependências • Verificação de procedência     │
├─────────────────────────────────────────────────────────┤
│  VERIFICAÇÃO EM TEMPO DE EXECUÇÃO                        │
│  • Uso inesperado de ferramentas  • Acesso a credenciais │
│  • Rede não documentada           • Padrões de egresso   │
├─────────────────────────────────────────────────────────┤
│  PÓS-VERIFICAÇÃO        Após concluir a auditoria        │
│  • Detecção de regressão  • Revisão de falsos positivos  │
│  • Calibração do scorer   • Geração de relatório         │
└─────────────────────────────────────────────────────────┘
```

---

### Loop de Auto-Melhoria

Este é o princípio de design central: **o auditor melhora através do seu próprio uso.**

Após cada varredura, `risk_scorer.py` emite `self_notes` — observações estruturadas sobre a qualidade da sua própria detecção. Essas notas são gravadas no log de auditoria e apresentadas nos relatórios. No próximo ciclo de iteração, o scorer lê suas próprias notas e propõe correções concretas — **aguardando confirmação humana** antes de aplicar as mudanças.

```
varredura → self_notes → proposta → confirmação humana → patch → re-varredura → verificação
```

**Histórico de versões impulsionado por auto-descoberta:**

| Versão | Gatilho | Correção |
|--------|---------|---------|
| v0.1.0 | Inicial | Scanner estático de 7 dimensões |
| v0.2.0 | Self-note: hits D1 em blocos de código | Excluir blocos ` ``` `; corrigir falso positivo D6 `>=`; reconstruir D7 |
| v0.2.1 | Análise automática do `cosmos-policy` | Padrão D2 `token` muito amplo — correspondia a vocabulário ML ("tokenizer") |

---

### Uso

```bash
git clone https://github.com/WilliamHe-cyber/claude-skills.git
cp -r claude-skills/skill-security-auditor ~/.claude/skills/
```

```
/security-audit                    # Varrer todas as skills
/security-audit langchain          # Varrer uma skill
/security-audit --log              # Ver resumo do log
/security-audit --iterate          # Ciclo de auto-melhoria
/security-audit --pre nova-skill   # Pré-verificação antes de instalar
```

---

### Auditorias Semanais Automatizadas

Este repositório executa um agente Claude Code automático toda **segunda-feira às 9h00** que varre todas as skills, detecta regressões, gera um relatório e — se houver `self_notes` pendentes — lista as melhorias propostas **aguardando confirmação humana** antes de modificar qualquer código.

Os relatórios de auditoria são públicos e versionados: [`skill-security-auditor/reports/`](./skill-security-auditor/reports/).

---

### Contribuindo

1. **Adicionar uma skill** — Crie `sua-skill/SKILL.md` e abra um PR. Skills com pontuação CRÍTICA ou BLOQUEADA não serão mescladas.
2. **Melhorar o scanner** — Abra uma issue descrevendo o falso positivo ou a detecção perdida.
3. **Notas de calibração** — Ao ajustar pesos, adicione uma entrada `## Calibration Note` em `scoring_matrix.md`.

---

### Licença

MIT — ver [LICENSE](./LICENSE)

*Construído com [Claude Code](https://claude.ai/claude-code) · Auditado por si mesmo · Auto-iterando desde v0.1.0*
