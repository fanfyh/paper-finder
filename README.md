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

### 2. 编辑兴趣画像

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

### 3. 使用

三种模式：

```bash
# 完整摘要流程：检查画像 → arXiv 检索 → 排序 → 输出 markdown
research-assist --action digest --config ~/.openclaw/skills/research-assist/config.json

# 临时搜索（不需要配置文件）
research-assist --action search --query "large language model reasoning" --top 5

# 检查画像刷新状态
research-assist --action profile-refresh --config ~/.openclaw/skills/research-assist/config.json
```

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
├── src/codex_research_assist/  # 源码
│   ├── __main__.py             # python -m 入口
│   ├── openclaw_runner.py      # CLI 入口（3 个 action）
│   ├── ranker.py               # 3 维评分引擎
│   ├── arxiv_profile_pipeline/ # arXiv 检索管线
│   └── controller/             # 画像刷新策略
├── references/                 # 合约与工作流文档
├── profiles/                   # 兴趣画像示例
├── automation/                 # 提示词模板 + 配置示例
└── reports/schema/             # JSON Schema
```

## 依赖

仅两个外部依赖：

- `feedparser` — 解析 arXiv Atom feed
- `requests` — HTTP 请求

其余全部使用 Python 标准库。
