---
name: paper-finder
description: OpenAlex + NBER 文献发现工具，支持基于 Zotero 兴趣图谱的语义排序和邮件/Telegram 推送。当用户想找论文、订阅每周文献周报、安装或重新配置 paper-finder 时使用此 skill。
---

# Paper-Finder Skill

## 何时激活

当用户说以下内容时激活此 skill：
- "帮我找关于 ___ 的论文" / "搜索 ___ 最新文献"
- "设置每日论文推送" / "我想订阅文献日报"
- "更新研究兴趣" / "paper-finder 配置不对"
- "安装 paper-finder" / "paper-finder 出问题了"
- "更新 paper-finder 配置" / "重新配置 paper-finder"

**即时搜索**：直接运行 CLI，不创建定时任务。
**每周订阅**：进入安装流程，创建每周二 09:00 的 cron job。

## 安装与配置流程

### 首次使用：按 `references/onboarding.md` 执行完整配置

完整配置流程分 5 步，agent 自动执行，用户只需确认结果：

1. **连接 Zotero** — 写入 library_id + api_key 到 config.json
2. **分析 Zotero 库** — 自动统计期刊频次，生成研究兴趣和目标期刊推荐
3. **确认配置** — agent 展示推荐列表，用户确认后写入
4. **验证检索** — 测试多期刊过滤是否正常工作
5. **创建定时任务** — 如需要，设置每周订阅 cron job

### 已完成配置后的常规使用

```bash
# 即时搜索（默认全局，检索所有来源）
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "housing policy" --top 20

# 基于研究兴趣的 digest（检索 config.json 中配置的期刊列表）
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action digest-all

# 仅搜索 NBER
paper-finder --action search --query "fiscal competition" --source nber --top 20
```

## 安装依赖

```bash
cd ~/.claude/tools/paper-finder && uv sync
```

## 验证连接

```bash
cd ~/.claude/tools/paper-finder && python -c "
import json, requests
cfg = json.load(open('config.json'))
h = {'Zotero-API-Key': cfg['zotero']['api_key'], 'Zotero-API-Version': '3'}
r = requests.get(f\"https://api.zotero.org/users/{cfg['zotero']['library_id']}/items?limit=1\", headers=h)
print('Zotero:', 'OK' if r.ok else f'失败 {r.status_code}')
"
```

## 即时搜索用法

## CLI Usage

```bash
# Global search (default, all sources)
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "fiscal competition" --top 20

# Search NBER only
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "fiscal competition" --source nber --top 20

# Search specific journal
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "housing" --source JPubE --top 20

# Subscribe to digest (based on research profile)
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action digest-all

# Sync Zotero to semantic index
uv run --project ~/.claude/tools/paper-finder \
  paper-finder --config ~/.claude/tools/paper-finder/config.json \
  --action sync-index

# Zotero MCP server (for semantic search + feedback writeback)
uv run --project ~/.claude/tools/paper-finder paper-finder-zotero-mcp
```

Default config path: `~/.claude/tools/paper-finder/config.json`

## Install-Time Behavior

Installation and reconfiguration are one-time operations.

## 配置检测逻辑（agent 加载 skill 时自动执行）

```
1. config.json 存在？
   └─ 不存在 → 引导进入 onboarding（步骤1）

2. config.json 有 "zotero" 字段且有效？
   └─ 无效 → 引导重新配置 Zotero

3. config.json 有 "retrieval.journal_sources"？
   └─ 无 → 执行 Zotero 库分析，生成推荐期刊 → 写入 config

4. config.json 有 "_onboarding_complete": true？
   └─ 无 → 提示"尚未完成初始配置"，引导完成剩余步骤

5. profiles/research-interest.json 存在且非空？
   └─ 无 → 引导生成或手动创建
```

## Hard rules for the host agent

- 首次加载 skill 时，**必须**执行配置检测，不跳过任何步骤
- 使用 `references/onboarding.md` 作为完整配置流程的参考
- 写入配置前必须**展示结果给用户，等待确认**（用户决策点）
- config.json 已有 `_onboarding_complete: true` 时，不重复询问已完成的步骤
- 配置写入后立即执行验证测试
- use `references/setup-routing.md` only when the user is installing, reconfiguring, or when required config is missing
- once `config.json` is valid, normal digest/search runs must not reopen setup questions
- when setup selects optional backends or delivery routes, execute the required install/setup commands
- before leaving setup, run a minimal verification for the selected backend

## Config Format

```json
{
  "profile_path": "~/.claude/tools/paper-finder/profiles/research-interest.json",
  "output_root": "/path/to/output",
  "zotero": {
    "library_id": "your_library_id",
    "api_key": "your_api_key"
  },
  "semantic_search": {
    "enabled": true,
    "zotero_db_path": "/path/to/zotero.sqlite"
  }
}
```

## Architecture

```
config.json
    ↓
openclaw_runner.py (CLI entry)
    ├── client.py           → OpenAlex API client
    ├── pipeline.py          → Retrieval pipeline (run_openalex_pipeline)
    ├── ranker.py           → scoring (keywords + semantic)
    └── html_fmt.py         → HTML digest output
```

No LLM calls inside the packaged Python pipeline. Retrieval, ranking, and formatting are pure data operations.

## Core Functions

### search — Paper Retrieval

Query OpenAlex API for papers by keyword.

**Default behavior**: Global search across all sources (no journal restriction).

**Optional sources** (only when explicitly specified):
- `nber` — NBER working papers only
- Journal aliases (see below) — Specific journal only

### Available Journal Sources

Journal list is loaded from `assets/journal_list.json`, containing **AAA & AA** journals from 中央财经大学期刊目录（2025版）.

**Summary (145 journals):**
- AAA: 68 journals
- AA: 87 journals

**Coverage:**
- Economics, Political Science, Sociology, Public Administration
- Business, Finance, Accounting, Law, and more

**Common aliases:**
- `AER` = American Economic Review
- `JPE` = Journal of Political Economy
- `APSR` = American Political Science Review
- `JPubE` = Journal of Public Economics
- `JPAM` = Journal of Policy Analysis and Management

To find a journal alias, check `assets/journal_list.json` or search by title.

### digest-all — Subscription Digest

Retrieve papers from configured sources based on research profile, rank by relevance, and deliver digest.

### sync-index — Zotero Semantic Index

Build or update the semantic search index from Zotero library.

### profile-refresh — Update Research Profile

Refresh research interest profile based on Zotero evidence.

## Zotero Integration (Optional)

### Semantic Search

When enabled, uses Zotero library as semantic reference for ranking:
- Extracts embeddings from Zotero items
- Finds semantically similar papers for each candidate
- Boosts ranking for papers close to your library

### Feedback Writeback

Non-destructive feedback system:

Allowed operations:
- Add tags (including decision tags like `ra-status:read_first`)
- Add or change collection membership
- Append notes to items
- Create new collections

Prohibited operations:
- Delete Zotero items or collections
- Modify item metadata (title, authors, abstract, DOI)
- Apply changes without dry-run preview first

## Hard Rules

- Search function works standalone, no Zotero required
- Prefer `dry_run=true` for any Zotero writeback
- Do not expand concise method labels into long topic sentences
- Do not make full text the default review mode
- Do not delete Zotero items or collections automatically

## Key Runtime Files

- CLI runner: `src/codex_research_assist/openclaw_runner.py`
- OpenAlex client: `src/codex_research_assist/client.py`
- Retrieval pipeline: `src/codex_research_assist/pipeline.py` (`run_openalex_pipeline`)
- Ranker: `src/codex_research_assist/ranker.py`
- Example config: `config.example.json`
- Example profile: `profiles/research-interest.example.json`

## Reference Documents

- `references/workflow.md` — workflow stages
- `references/contracts.md` — data contracts
- `references/setup-routing.md` — install-time setup guide
- `references/onboarding.md` — **完整配置流程（首次使用必读）**
- `references/cronjob_prompt.md` — 定时任务 prompt 模板
- `references/zotero-mcp.md` — Zotero MCP server
