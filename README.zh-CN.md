# Paper-Finder：基于 OpenAlex 的经济学文献发现工具

通过 OpenAlex API 检索 NBER 工作论文和顶级经政期刊论文，根据你的研究兴趣智能推荐。

---

## 核心功能

| 功能 | 说明 | 依赖 |
|------|------|------|
| **检索论文** | 按 NBER、17期刊或全库搜索关键词 | 无 |
| **订阅推送** | 根据研究兴趣定期推送新论文 | 研究画像配置 |
| **（可选）Zotero 增强** | 用你的 Zotero 文库优化排序 | Zotero + 语义搜索 |

---

## 快速开始

### 基础检索

```bash
# 搜索 NBER 工作论文
export PATH="$HOME/.local/bin:$PATH" && \
uv run --project ~/.claude/tools/paper-finder \
  research-assist --config ~/.claude/tools/paper-finder/config.json \
  --action search --query "fiscal competition" --source nber --top 20

# 搜索特定期刊
--action search --query "housing" --source JPE --top 20

# 搜索 OpenAlex 全库
--action search --query "urban economics" --source openalex --top 20
```

### 订阅推送

首次使用需要配置研究画像（见下方配置说明），然后：

```bash
# 检查并推送新论文
--action digest-all
```

### Zotero 增强（可选）

```bash
# 同步 Zotero 到语义索引
--action sync-index

# 更新研究画像
--action profile-refresh
```

---

## 使用场景

### 场景 1：月度订阅更新

**目标**：按你选定的期刊或来源（如 NBER），定期检索新论文，根据研究兴趣推送。

**用法**：
1. 在 `research-interest.json` 中配置你的研究兴趣
2. 运行 `digest-all` 命令
3. 系统会检索近一个月的论文，按兴趣匹配度排序
4. 结果可通过邮件或 HTML 查看方式推送

### 场景 2：反馈学习（可选）

**目标**：对推送的论文打分，迭代优化研究画像。

**用法**：
1. 推送后对每篇论文标记状态（`read_first`、`skim`、`archive`、`skip_for_now` 等）
2. 系统将反馈写回 Zotero（tags、collections、notes）
3. 下次推送时会参考反馈调整排序

### 场景 3：语义检索

**目标**：基于语义分析检索相关文献，而非简单关键词匹配。

**用法**：
- 需要启用 Zotero 语义搜索
- 系统会使用你的 Zotero 文库作为语义参考
- 返回的论文会标注"最相似的 Zotero 条目"

### 场景 4：期刊偏好分析（计划中）

**目标**：选定期刊，回顾近一年论文，识别选题偏好。

**状态**：待实现

---

## 数据来源

### NBER 工作论文

直接检索 NBER 发布的工作论文，覆盖所有研究项目。

### 17本经政期刊

| 简写 | 期刊 |
|------|------|
| AER | American Economic Review |
| JPE | Journal of Political Economy |
| QJE | Quarterly Journal of Economics |
| RES | Review of Economic Studies |
| REStat | Review of Economics and Statistics |
| EJ | Economic Journal |
| Econometrica | Econometrica |
| JPubE | Journal of Public Economics |
| JDE | Journal of Development Economics |
| JUE | Journal of Urban Economics |
| AJPS | American Journal of Political Science |
| APSR | American Political Science Review |
| BJPS | British Journal of Political Science |
| PA | Political Analysis |
| WP | World Politics |
| Governance | Governance |
| RP | Research Policy |

### OpenAlex 全库

不限定期刊，检索整个 OpenAlex 数据库。

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户输入                               │
│  关键词检索 / 研究画像 / Zotero 文库（可选）                    │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     OpenAlex 检索层                          │
│  NBER API / 期刊过滤 / 全库搜索                               │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       匹配与排序                              │
│  关键词匹配 / 研究画像评分 / Zotero 语义相似度（可选）           │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       输出与反馈                              │
│  HTML digest / 邮件推送 / Zotero 写回（可选）                   │
└─────────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **检索优先** — 核心是 OpenAlex 检索，Zotero 只是可选增强
2. **流式处理** — 检索、排序、输出是分离的阶段
3. **非破坏性反馈** — Zotero 写回默认 `dry_run=true`
4. **Agent 原生** — 可与 Claude Code 等 LLM 工具集成

---

## 配置文件

### config.json

主要配置文件，位于 `~/.claude/tools/paper-finder/config.json`。

**关键配置项**：

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
  },
  "delivery": {
    "primary_channel": "email",
    "email": {
      "send_enabled": true,
      "recipients": ["your@email.com"]
    }
  }
}
```

### research-interest.json

研究画像配置，定义你的研究兴趣。

**结构**：

```json
{
  "interests": [
    {
      "interest_id": "public-finance",
      "label": "Public Finance",
      "enabled": true,
      "method_keywords": ["tax", "fiscal", "government spending"],
      "query_aliases": ["taxation", "public finance", "fiscal policy"],
      "exclude_keywords": [],
      "logic": "OR"
    }
  ]
}
```

---

## 命令参考

### search — 检索论文

```bash
--action search --query "关键词" --source <SOURCE> --top N
```

| 参数 | 说明 |
|------|------|
| `--query` | 检索关键词 |
| `--source` | 来源：`nber` / `JPE,AER,...` / `all` / `openalex` |
| `--top` | 返回结果数量 |

### digest-all — 订阅推送

```bash
--action digest-all
```

按研究画像检索新论文并推送。

### sync-index — Zotero 同步

```bash
--action sync-index
```

将 Zotero 文库同步到语义搜索索引。

### profile-refresh — 更新画像

```bash
--action profile-refresh
```

根据 Zotero 文库更新研究画像。

---

## 开发

### 安装依赖

```bash
cd ~/.claude/tools/paper-finder
uv sync
```

### 运行测试

```bash
uv run pytest
```

---

## 参考文档

- [`SKILL.md`](SKILL.md) — Skill 契约规范
- [`references/workflow.md`](references/workflow.md) — 工作流详细说明
- [`references/contracts.md`](references/contracts.md) — 数据契约定义
