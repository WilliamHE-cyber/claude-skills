# claude-skills

**Language / 语言 / Idioma / Langue / Idioma / 言語**
[English](./README.md) · [中文](./README.zh.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Português](./README.pt.md) · [日本語](./README.ja.md)

---

> **权威来源：** 本仓库 [github.com/WilliamHE-cyber/claude-skills](https://github.com/WilliamHE-cyber/claude-skills) 是唯一官方版本。可能存在 Fork 和镜像，如有疑问，以本仓库的审计历史和已批准版本为准。Copyright © WilliamHE-cyber。

一个经过安全审计的 Claude Code skills 精选集合。
所有 skill 在发布前均由内置的 `skill-security-auditor` 每周自动扫描。

---

## Skills 列表

| Skill | 版本 | 风险评分 | 说明 |
|-------|------|---------|------|
| [skill-security-auditor](./skill-security-auditor/) | 0.2.1 | 自豁免 | 从 7 个维度审计 Claude skills 的安全风险，具备自我迭代能力 |

---

## skill-security-auditor

> **一个面向 Claude Code skills 的 MVP 安全审计工具——设计目标是发现自身盲点并持续修复。**

### 问题背景

Claude Code skills 是指导 Claude 执行 shell 命令、调用外部 API、读写文件和处理凭证的 Markdown 文件。一个恶意或编写不当的 skill 可能导致数据外泄、执行任意代码或静默泄漏 API 密钥。目前没有标准方法在加载 skill 之前评估其风险。

### 功能介绍

`skill-security-auditor` 对 `~/.claude/skills/` 目录下的每个 skill 进行静态分析，从 7 个风险维度打分，生成结构化报告，维护仅追加的审计日志，并将自身检测逻辑的缺陷记录下来以便持续改进。

---

### 7 维度风险评分矩阵

每个维度评分 **0–10**，加权合并得到最终 **0–100** 分。

| # | 维度 | 权重 | 检测内容 |
|---|------|------|---------|
| D1 | **网络暴露** | 20% | 外部 HTTP 调用、动态 URL 构造、原始套接字 |
| D2 | **凭证访问** | 20% | API 密钥、Token、`.env` 文件、钥匙串访问 |
| D3 | **代码执行** | 18% | `subprocess`、`eval`、`exec`、`sudo`、管道执行 |
| D4 | **文件系统访问** | 15% | 读写工作区外文件、访问 `~/.ssh`、`~/.aws` |
| D5 | **数据外泄** | 12% | 对话数据外传、Base64 编码载荷 |
| D6 | **依赖风险** | 8% | `git+` URL、未固定版本、非标准包源 |
| D7 | **提示注入面** | 7% | 抓取的外部内容未经净化直接注入提示词 |

**风险等级：**

| 分数 | 等级 | 处置方式 |
|------|------|---------|
| 0–19 | 🟢 低风险 | 无需处理 |
| 20–39 | 🟡 中风险 | 30 天内审查 |
| 40–59 | 🟠 高风险 | 7 天内审查 |
| 60–79 | 🔴 严重 | 隔离待审查 |
| 80–100 | ⛔ 封锁 | 禁止加载，需人工审批 |

---

### 三层检查协议

```
┌─────────────────────────────────────────────────────────┐
│  预检（PRE-CHECK）       加载 skill 之前                  │
│  • 解析 frontmatter      • 黑名单查询（30天窗口）          │
│  • 依赖扫描              • 作者来源核查                   │
├─────────────────────────────────────────────────────────┤
│  运行检查（RUNTIME）     skill 执行期间                   │
│  • 未预期的工具调用       • 凭证环境变量访问               │
│  • 未记录的网络请求       • 数据外传模式                   │
├─────────────────────────────────────────────────────────┤
│  后检（POST-CHECK）      审计完成后                       │
│  • 回归检测              • 误报审查                       │
│  • 评分器校准            • 报告生成                       │
└─────────────────────────────────────────────────────────┘
```

---

### 自我迭代循环

这是核心设计理念：**审计工具通过使用本身来提升自身能力。**

每次扫描后，`risk_scorer.py` 会生成 `self_notes`——对自身检测质量的结构化观察：

- 疑似误报（评分低但命中多）
- 逻辑反转或过于宽泛的信号模式
- 已知高危模式的漏报

这些记录写入审计日志并在报告中呈现。下一次迭代时，评分器读取自身的 notes，提出对 `SIGNALS` 模式、权重或评分逻辑的具体修改建议——**等待人工确认后**再执行变更。

```
扫描 → self_notes → 改进提案 → 人工确认 → 应用补丁 → 重新扫描 → 验证
```

**由自我发现驱动的版本历史：**

| 版本 | 触发原因 | 修复内容 |
|------|---------|---------|
| v0.1.0 | 初始版本 | 7 维度静态扫描器 |
| v0.2.0 | Self-note：D1 命中均在代码块中 | 排除 ` ``` ` 代码块扫描；修复 D6 `>=` 误报；重建 D7 |
| v0.2.1 | 对 `cosmos-policy` 的自动散文分析 | 收窄 D2 `token` 模式——原先误匹配 ML 词汇（"tokenizer"、"离散 token"） |

---

### 使用方式

将 skill 目录放入 `~/.claude/skills/`：

```bash
git clone https://github.com/WilliamHE-cyber/claude-skills.git
cp -r claude-skills/skill-security-auditor ~/.claude/skills/
```

在任意 Claude Code 会话中使用：

```
# 扫描所有已安装的 skills
/security-audit

# 扫描单个 skill
/security-audit langchain

# 查看审计日志摘要
/security-audit --log

# 触发自我改进周期
/security-audit --iterate

# 安装前预检
/security-audit --pre some-new-skill
```

**输出示例：**

```
============================================================
  SKILL RISK REPORT — autogpt
============================================================
  分数: 37.6/100   [中风险]
  处置: 30 天内审查

  维度详情：
    D1_network             4.0/10  [####      ]  贡献=8.00
      L  44: [HTTP URL 字面量]  git clone https://github.com/...
    D2_credentials         5.0/10  [#####     ]  贡献=10.00
      L  48: [.env 文件引用]  cp .env.example .env

  评分器自检记录（待迭代）：
    ⚙ D1：所有网络命中均为文档示例中的 URL 字面量，疑似误报
============================================================
```

---

### 自动化周报

本 repo 每**周一上午 9:00** 运行一个自动 Claude Code Agent，流程如下：

1. 全新 clone 本 repo
2. 用 `risk_scorer.py` 运行全量扫描
3. 检测回归（与上次扫描相比分数上升超 10 分）
4. 在 `skill-security-auditor/reports/` 生成报告
5. 若 `self_notes` 不为空：列出改进提案，**等待人工确认**后才修改代码
6. 将报告 commit 回 repo

审计报告公开可查，完整历史见 [`skill-security-auditor/reports/`](./skill-security-auditor/reports/)。

---

### 架构

```
skill-security-auditor/
├── SKILL.md                      入口——Claude 的执行指令
├── references/
│   ├── risk_scorer.py            静态扫描器（Python，可独立运行）
│   ├── scoring_matrix.md         7 维度评分标准 + 校准历史
│   └── audit_log_schema.md       JSONL 审计日志格式 + 查询示例
└── templates/
    └── audit_report.md           周报模板
```

---

### 贡献指南

1. **新增 skill** — 创建 `your-skill-name/SKILL.md` 并开 PR。周报自动运行；评分为 CRITICAL 或 BLOCKED 的 skill 不会被合并。
2. **改进扫描器** — 发现误报或漏报？开 Issue 说明 skill 名、命中行和原因；或在本地运行 `/security-audit --iterate` 并附上建议的 diff。
3. **校准记录** — 调整权重或阈值时，在 `scoring_matrix.md` 添加 `## Calibration Note`，注明日期和理由。

---

### 许可证

MIT — 详见 [LICENSE](./LICENSE)

*由 [Claude Code](https://claude.ai/claude-code) 构建 · 由自身审计 · 从 v0.1.0 起持续自我迭代*
