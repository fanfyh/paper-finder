# research-assist

轻量 arXiv 文献摘要 skill，基于 Zotero 兴趣画像 + 3 维候选排序 + abstract-first 审阅。

## 安装

```bash
cd research-assist
uv sync
```

## 快速开始

### 1. 准备配置

```bash
# 创建 OpenClaw skill 目录
mkdir -p ~/.openclaw/skills/research-assist/profiles
mkdir -p ~/.openclaw/skills/research-assist/reports

# 复制示例配置
cp config.example.json ~/.openclaw/skills/research-assist/config.json

# 复制示例兴趣画像（按需编辑）
cp profiles/research-interest.example.json \
   ~/.openclaw/skills/research-assist/profiles/research-interest.json
```

### 2. 配置 Zotero（用于画像与反馈）

两种方式任选其一：

1) 在 `~/.openclaw/skills/research-assist/.env` 写入：

```bash
ZOTERO_LIBRARY_ID="..."
ZOTERO_API_KEY="..."
ZOTERO_LIBRARY_TYPE="user"
```

2) 或在 `~/.openclaw/skills/research-assist/config.json` 的 `zotero` 块里填写（见 `config.example.json`）。

如果你希望 Claw / agent 只使用群组库，而不是整个个人库，建议固定成：

```json
{
  "zotero": {
    "library_type": "group",
    "library_id": "6433210",
    "enforce_library_type": "group",
    "enforce_library_id": "6433210"
  },
  "semantic_search": {
    "local_group_id": 6433210
  }
}
```

这样有两层限制：

- Web API 工具只能访问 group `6433210`
- 本地 sqlite 语义索引只读取这个 group 对应的本地 library

启动 MCP server（给上层 agent 调用）：

```bash
research-assist-zotero-mcp
```

语义搜索首次使用前建议先建立索引：

```bash
uv run python - <<'PY'
from codex_research_assist.zotero_mcp.semantic_search import create_semantic_search

search = create_semantic_search()
print(search.update_database(force_rebuild=False))
PY
```

前提：

- 必须先在配置里提供本地 `zotero.sqlite` 路径
- 也就是 `semantic_search.zotero_db_path`
- 当前这条语义搜索链默认要求本地数据库，不再用 Zotero Web API 代替

### 3. 编辑兴趣画像

编辑 `~/.openclaw/skills/research-assist/profiles/research-interest.json`，按照 `references/contracts.md` 中的 profile contract 格式填写你的研究兴趣：

```json
{
  "interests": [
    {
      "label": "Gaussian Process",
      "enabled": true,
      "method_keywords": ["gaussian process", "GP regression"],
      "query_aliases": ["deep kernel learning", "neural process"],
      "exclude_keywords": ["unrelated-term"]
    }
  ]
}
```

### 4. 使用

三种模式：

```bash
# 完整摘要流程：检查画像 → arXiv 检索 → 排序 → 输出 markdown
research-assist --action digest --config ~/.openclaw/skills/research-assist/config.json

# 临时搜索（不需要配置文件）
research-assist --action search --query "large language model reasoning" --top 5

# 检查画像刷新状态
research-assist --action profile-refresh --config ~/.openclaw/skills/research-assist/config.json
```

### 4.1 刷新画像（完整闭环）

当前仓库的 CLI 只检查 refresh policy，不会直接生成画像。完整画像刷新由 controller 脚本执行，它会：

- 通过 `research-assist-zotero-mcp` 读取 Zotero 证据
- 产出并规范化 profile JSON
- 回写 `profiles/research-interest.json`

执行：

```bash
bash scripts/profile/refresh_profile.sh --config automation/arxiv-profile-digest.example.toml
```

### 4.2 Zotero MCP 现在能做什么

- 语义搜索：`zotero_semantic_search`
- 刷新本地索引：`zotero_update_search_database`
- 精确搜索 item：`zotero_search_items`
- 批量加/删 tag：`zotero_batch_update_tags`
- 建 collection / 调整父子结构：`zotero_create_collection`、`zotero_update_collection`
- 将 item 加入或移出 collection：`zotero_move_items_to_collection`
- 非破坏性反馈写回：`zotero_apply_feedback`

当前不支持：

- 直接搬动 Zotero `storage/` 目录里的附件物理文件
- 自动删除 item 或 collection

### 4.3 本地模型语义搜索

这里保留两条路线：

1. 正式本地模型路线：使用你现有的 `Qwen/Qwen3-Embedding-0.6B`
2. 轻量测试路线：使用 `fastembed`，只用于 smoke test / 快速验通

#### 方案 A：`Qwen/Qwen3-Embedding-0.6B`

如果要启用你现有的本地 embedding 模型：

```bash
cd /home/zlg/code/research-assist-zotero-wt
uv sync --extra semantic-local
```

然后把 `semantic_search.embedding_model` 设置成：

```json
{
  "semantic_search": {
    "zotero_db_path": "~/Zotero/zotero.sqlite",
    "embedding_model": "Qwen/Qwen3-Embedding-0.6B"
  }
}
```

#### 方案 B：`fastembed` 轻量测试

如果只是快速测试索引链是否能跑通：

```bash
cd /home/zlg/code/research-assist-zotero-wt
uv sync --extra semantic-fastembed
```

然后配置成：

```json
{
  "semantic_search": {
    "zotero_db_path": "~/Zotero/zotero.sqlite",
    "embedding_model": "fastembed"
  }
}
```

可选地再通过环境变量指定具体 fastembed 模型：

```bash
export FASTEMBED_MODEL="BAAI/bge-small-en-v1.5"
```

共同前提：

- 本地模型语义搜索要求先准备好本地 `zotero.sqlite`
- 如果没有这个文件，`zotero_update_search_database` 会直接报错
- `fastembed` 这条路线在当前仓库里主要用于轻量测试，不替代你现有的主模型配置

### 4.4 轻量本地库方案（适合 Claw 维护）

不建议在 skill 里“安装另一个 Zotero 实例”。更轻量、也更稳的做法是：

1. 使用你 Windows 上已经安装好的 Zotero Desktop  
   例如当前快捷方式指向：
   `C:\\Program Files\\Zotero\\zotero.exe`

2. 让 Zotero Desktop 负责同步群组库到本地数据目录

3. 在 skill 配置里把 `semantic_search.zotero_db_path` 指向这份本地 `zotero.sqlite`

4. 再通过：
   - `zotero.enforce_library_type = group`
   - `zotero.enforce_library_id = 6433210`
   - `semantic_search.local_group_id = 6433210`

   把 agent 的可见范围限制在这个群组库

这样做的优点是：

- 不需要在 skill 内维护 GUI Zotero 安装
- Claw 只依赖本地同步好的数据库文件
- Web API 与本地语义索引都能同时限定在 group `6433210`

也可以用 Python module 方式调用：

```bash
python3 -m codex_research_assist --action search --query "transformer" --top 3
```

### 4. 输出

所有输出为 markdown 格式，打印到 stdout。日志输出到 stderr。

digest 输出示例：

```
# arXiv Research Digest 2026-03-11

Found 5 new papers:

## 1. Neural Scaling Laws for Language Models
**Authors:** Author A, Author B, Author C et al.
**arXiv ID:** 2503.09999
**Matched Interests:** LLM scaling
**Score:** 0.91 (rel=0.85 rec=1.00 nov=1.00)

**Abstract:** We study the scaling behavior of large language models...
```

## 排序算法

3 维加权评分，每个维度归一化到 [0, 1]：

| 维度 | 权重 | 说明 |
|---|---|---|
| relevance | 0.60 | 每个关键词短语独立匹配，取最高分 |
| recency | 0.25 | 7 天内满分，之后指数衰减 |
| novelty | 0.15 | 未见过 = 1.0，已见过 = 0.0 |

## 目录结构

```
research-assist/
├── SKILL.md                    # Skill 定义（OpenClaw 读取）
├── config.example.json         # OpenClaw 配置示例
├── pyproject.toml              # Python 包定义
├── uv.lock                     # 锁定依赖
├── scripts/                    # controller 辅助脚本（profile refresh 等）
├── src/codex_research_assist/  # 源码
│   ├── __main__.py             # python -m 入口
│   ├── openclaw_runner.py      # CLI 入口（3 个 action）
│   ├── ranker.py               # 3 维评分引擎
│   ├── arxiv_profile_pipeline/ # arXiv 检索管线
│   ├── controller/             # 画像刷新策略
│   └── zotero_mcp/             # Zotero MCP server（读 Zotero 证据 + 非破坏性写回）
├── references/                 # 合约与工作流文档
├── profiles/                   # 兴趣画像示例
├── automation/                 # 提示词模板 + 配置示例
└── reports/schema/             # JSON Schema
```

## 依赖

核心依赖：

- `feedparser` — 解析 arXiv Atom feed
- `requests` — HTTP 请求
- `pyzotero` — Zotero Web API 客户端（通过 MCP 读写）
- `fastmcp` — MCP server 运行时
- `python-dotenv` — 从 `.env` 读取 Zotero 密钥

其余为上述依赖的传递依赖，由 `uv.lock` 固定版本。
