# Paper-Finder 配置流程

首次安装或重新配置时，按以下步骤执行。

---

## 步骤 1：连接 Zotero

### 1a. 获取 Zotero API 凭证

1. 登录 [Zotero](https://www.zotero.org) → Settings → Feeds/API
2. 创建新的 API key（只显示一次，保存好）
3. 库 ID 在同一页面查看

### 1b. 写入配置

```bash
# 写入 zotero 凭证
cd ~/.claude/tools/paper-finder
cp config.example.json config.json
# 编辑 config.json，填入 library_id 和 api_key
```

config.json 中的位置：
```json
{
  "zotero": {
    "library_id": "你的library_id",
    "api_key": "你的api_key"
  }
}
```

### 1c. 验证连接

```bash
uv run --project . python -c "
import json, requests
cfg = json.load(open('config.json'))
h = {'Zotero-API-Key': cfg['zotero']['api_key'], 'Zotero-API-Version': '3'}
r = requests.get(f\"https://api.zotero.org/users/{cfg['zotero']['library_id']}/items?limit=1\", headers=h)
print('Zotero连接:', 'OK' if r.ok else f'失败 {r.status_code}')
"
```

---

## 步骤 2：分析 Zotero 库 → 生成研究兴趣和目标期刊

**这一步由 agent 自动完成**，用户只需确认结果。

Agent 执行以下操作：
1. 抓取 Zotero 库全部文献元数据（publicationTitle 字段）
2. 统计英文期刊出现频次（过滤掉无英文标题的）
3. 对照 `assets/journal_list.json`（中央财经大学 CESCI AAA/AA 目录）标记每本期刊的级别
4. 输出：
   - **研究兴趣关键词**（从 tags + titles 提取）
   - **推荐目标期刊列表**（用户 Zotero 库中高频出现的 AAA/AA 期刊，top 15）

### Agent 输出模板

```
📊 Zotero 库分析结果（共 N 条文献）

【推荐目标期刊 Top 15】（按你库中出现频次排序）
  1. Journal of Public Economics — N篇 — AAA
  2. American Economic Review — N篇 — AAA
  ...（共15本）

【建议研究方向】（从 tags 提取）
  - 城市空间均衡与住房政策
  - 地方政府财政激励
  - 劳动力流动与区域发展

是否确认以上配置？确认后写入 config.json 和 profiles/research-interest.json
```

### 用户决策点

- **确认** → 写入配置文件
- **修改** → 调整期刊列表或研究方向
- **仅查看** → 不写入，继续手动配置

---

## 步骤 3：写入配置文件

Agent 获得确认后，执行以下写入：

### 3a. 更新 `config.json`

新增字段：
```json
{
  "retrieval": {
    "journal_sources": [
      {"title": "Journal of Public Economics", "openalex_id": "S199447588"},
      {"title": "American Economic Review", "openalex_id": "S23254222"},
      {"title": "Journal of Urban Economics", "openalex_id": "S147692640"},
      {"title": "Journal of Development Economics", "openalex_id": "S101209419"},
      {"title": "The China Quarterly", "openalex_id": "S12189451"},
      {"title": "The Quarterly Journal of Economics", "openalex_id": "S203860005"},
      {"title": "Journal of Political Economy", "openalex_id": "S95323914"},
      {"title": "Journal of the European Economic Association", "openalex_id": "S165087003"},
      {"title": "Journal of Comparative Economics", "openalex_id": "S138645024"},
      {"title": "Journal of International Economics", "openalex_id": "S198098467"},
      {"title": "World Development", "openalex_id": "S85457386"},
      {"title": "Journal of Economic Growth", "openalex_id": "S181171746"},
      {"title": "The Review of Economic Studies", "openalex_id": "S88935262"},
      {"title": "Social Policy & Administration", "openalex_id": "S31120751"},
      {"title": "American Political Science Review", "openalex_id": "S176007004"}
    ]
  }
}
```

### 3b. 更新 `profiles/research-interest.json`

从步骤2自动生成，包含4-6个研究方向，每个方向有：
- 关键词（用于 OpenAlex 检索）
- query_aliases（扩展检索词）
- 方法论偏好（RD/DID/IV）

### 3c. 标记配置完成

在 `config.json` 写入时，同时写入：
```json
{
  "_onboarding_complete": true,
  "_onboarding_at": "2026-04-30"
}
```

---

## 步骤 4：验证检索

```bash
# 测试：从指定期刊列表检索最近7天的文献
cd ~/.claude/tools/paper-finder
uv run --project . python -c "
from codex_research_assist.pipeline import run_openalex_pipeline
from pathlib import Path
import json

cfg = json.load(open('config.json'))
journals = cfg['retrieval']['journal_sources']
print(f'检索期刊数: {len(journals)}')

# 对每个期刊执行一次检索（取前3条）
from codex_research_assist.client import search_works, parse_paper
for j in journals[:3]:
    papers = search_works(
        keywords=['housing', 'public economics', 'fiscal'],
        source=j['openalex_id'],
        from_date='2026-04-23',
        per_page=3
    )
    print(f\"  {j['title']}: {len(papers)} 篇\")
"
```

预期：每个期刊返回0-3篇（如果最近7天有相关新文献）

---

## 步骤 5：创建每周订阅（可选）

```bash
# 创建 cron job，每周二 09:00 执行
# 交付目标：飞书 DM
```

---

## 配置检测逻辑（供 agent 使用）

当 agent 加载 paper-finder skill 时，按以下顺序检测：

```
1. config.json 是否存在？
   └─ 不存在 → 引导进入步骤1（连接Zotero）

2. config.json 是否有 "zotero" 字段且有效？
   └─ 无效 → 引导重新配置 Zotero

3. config.json 是否有 "retrieval.journal_sources"？
   └─ 无 → 调用步骤2分析Zotero库，生成推荐 → 步骤3写入

4. config.json 是否有 "_onboarding_complete": true？
   └─ 无 → 提示用户尚未完成初始配置

5. profiles/research-interest.json 是否存在且非空？
   └─ 无 → 引导生成或手动创建
```

---

## 配置文件字段说明

| 字段 | 位置 | 说明 |
|------|------|------|
| `zotero.library_id` | config.json | Zotero 库 ID |
| `zotero.api_key` | config.json | Zotero API key |
| `retrieval.journal_sources` | config.json | 目标期刊列表（含 OpenAlex ID） |
| `retrieval_defaults.since_days` | config.json | 检索回溯天数（默认7） |
| `retrieval_defaults.max_results_per_interest` | config.json | 每个兴趣最多返回篇数 |
| `_onboarding_complete` | config.json | 配置是否完成（布尔） |
| `interests` | profiles/research-interest.json | 研究方向列表 |
