# claude-skills

**Language / 语言 / Idioma / Langue / Idioma / 言語**
[English](./README.md) · [中文](./README.zh.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Português](./README.pt.md) · [日本語](./README.ja.md)

---

Una colección curada de skills para Claude Code, auditadas en seguridad.
Cada skill es analizada semanalmente por el `skill-security-auditor` integrado antes de su publicación.

---

## Skills

| Skill | Versión | Puntuación de Riesgo | Descripción |
|-------|---------|----------------------|-------------|
| [skill-security-auditor](./skill-security-auditor/) | 0.2.1 | auto-exento | Audita skills de Claude en 7 dimensiones de riesgo con capacidad de auto-mejora |

---

## skill-security-auditor

> **Un auditor de seguridad MVP para skills de Claude Code — diseñado para encontrar sus propios puntos ciegos y corregirlos.**

### El Problema

Las skills de Claude Code son archivos Markdown que instruyen a Claude para ejecutar comandos de shell, llamar APIs externas, leer y escribir archivos, y manejar credenciales. Una skill maliciosa o mal escrita podría exfiltrar datos, ejecutar código arbitrario o filtrar claves API silenciosamente. Actualmente no existe un método estándar para evaluar el riesgo de una skill antes de cargarla.

### Qué Hace Esta Skill

`skill-security-auditor` realiza análisis estático en cada skill del directorio `~/.claude/skills/`. Puntúa cada skill en 7 dimensiones de riesgo, produce informes estructurados, mantiene un registro de auditoría de solo-adición y — lo más importante — señala las deficiencias en su propia lógica de detección para mejorar con el tiempo.

---

### Matriz de Puntuación de Riesgo en 7 Dimensiones

Cada dimensión se puntúa de **0 a 10** y se combina en una puntuación final de **0 a 100**.

| # | Dimensión | Peso | Qué Detecta |
|---|-----------|------|-------------|
| D1 | **Exposición de Red** | 20% | Llamadas HTTP externas, construcción dinámica de URLs, sockets en bruto |
| D2 | **Acceso a Credenciales** | 20% | Claves API, tokens, archivos `.env`, acceso al llavero |
| D3 | **Ejecución de Código** | 18% | `subprocess`, `eval`, `exec`, `sudo`, pipe-to-shell |
| D4 | **Acceso al Sistema de Archivos** | 15% | Lectura/escritura fuera del workspace, acceso a `~/.ssh`, `~/.aws` |
| D5 | **Exfiltración de Datos** | 12% | Datos de conversación enviados externamente, payloads codificados en Base64 |
| D6 | **Riesgo de Dependencias** | 8% | URLs `git+`, versiones sin fijar, índices no-PyPI |
| D7 | **Superficie de Inyección de Prompts** | 7% | Contenido externo insertado en prompts sin sanitización |

**Niveles de riesgo:**

| Puntuación | Nivel | Acción |
|------------|-------|--------|
| 0–19 | 🟢 BAJO | Sin acción requerida |
| 20–39 | 🟡 MEDIO | Revisar en 30 días |
| 40–59 | 🟠 ALTO | Revisar en 7 días |
| 60–79 | 🔴 CRÍTICO | Poner en cuarentena |
| 80–100 | ⛔ BLOQUEADO | No cargar; requiere aprobación humana |

---

### Protocolo de Verificación en Tres Capas

```
┌─────────────────────────────────────────────────────────┐
│  PRE-VERIFICACIÓN       Antes de cargar una skill        │
│  • Parsear frontmatter  • Consulta de lista negra        │
│  • Escaneo de deps      • Verificación de procedencia    │
├─────────────────────────────────────────────────────────┤
│  VERIFICACIÓN EN TIEMPO DE EJECUCIÓN                     │
│  • Uso inesperado de herramientas  • Acceso a credenciales│
│  • Red no documentada              • Patrones de egreso  │
├─────────────────────────────────────────────────────────┤
│  POST-VERIFICACIÓN      Después de completar la auditoría│
│  • Detección de regresión  • Revisión de falsos positivos│
│  • Calibración del scorer  • Generación de informe       │
└─────────────────────────────────────────────────────────┘
```

---

### Bucle de Auto-Mejora

Este es el principio de diseño central: **el auditor mejora a través de su propio uso.**

Después de cada escaneo, `risk_scorer.py` emite `self_notes` — observaciones estructuradas sobre su propia calidad de detección. Estas notas se escriben en el registro de auditoría y se presentan en los informes. En el siguiente ciclo de iteración, el scorer lee sus propias notas y propone correcciones concretas — **esperando confirmación humana** antes de aplicar cambios.

```
escaneo → self_notes → propuesta → confirmación humana → parche → re-escaneo → verificación
```

**Historial de versiones impulsado por auto-descubrimiento:**

| Versión | Disparador | Corrección |
|---------|-----------|------------|
| v0.1.0 | Inicial | Escáner estático de 7 dimensiones |
| v0.2.0 | Self-note: hits D1 dentro de bloques de código | Excluir bloques ` ``` `; corregir falso positivo D6 `>=`; reconstruir D7 |
| v0.2.1 | Análisis automático de `cosmos-policy` | Patrón D2 `token` demasiado amplio — coincidía con vocabulario ML ("tokenizer") |

---

### Uso

```bash
git clone https://github.com/WilliamHE-cyber/claude-skills.git
cp -r claude-skills/skill-security-auditor ~/.claude/skills/
```

```
/security-audit                    # Escanear todas las skills
/security-audit langchain          # Escanear una skill
/security-audit --log              # Ver resumen del registro
/security-audit --iterate          # Ciclo de auto-mejora
/security-audit --pre nueva-skill  # Pre-verificación antes de instalar
```

---

### Auditorías Semanales Automatizadas

Este repositorio ejecuta un agente Claude Code automático cada **lunes a las 9:00 AM** que escanea todas las skills, detecta regresiones, genera un informe y — si hay `self_notes` pendientes — lista las mejoras propuestas **esperando confirmación humana** antes de modificar cualquier código.

Los informes de auditoría son públicos y versionados: [`skill-security-auditor/reports/`](./skill-security-auditor/reports/).

---

### Contribuciones

1. **Agregar una skill** — Crea `tu-skill/SKILL.md` y abre un PR. Las skills con puntuación CRÍTICA o BLOQUEADA no serán fusionadas.
2. **Mejorar el escáner** — Abre un issue describiendo el falso positivo o la detección perdida.
3. **Notas de calibración** — Al ajustar pesos, añade una entrada `## Calibration Note` en `scoring_matrix.md`.

---

### Licencia

MIT — ver [LICENSE](./LICENSE)

*Construido con [Claude Code](https://claude.ai/claude-code) · Auditado por sí mismo · Auto-iterando desde v0.1.0*
