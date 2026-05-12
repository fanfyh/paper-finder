# paper-finder 重构计划

## 目标

将 `openalex_pipeline/client.py` 重构为完全由两个 JSON 文件驱动的状态：
- `journal_list.json` — 期刊别名 + source ID
- `working_paper_sources.json` — 工作论文机构别名 + institution ID

**约束：零硬编码 ID**（无 `_BUILTIN_REPOS`，无 `_MANUAL_JOURNAL_ALIASES`）。

---

## 当前问题诊断

### 问题 1：`_title_to_alias()` 生成的简称与实际常用名不匹配

| 期刊名 | `_title_to_alias()` 输出 | 常用名 |
|--------|--------------------------|--------|
| Journal of Political Economy | `JPECO` | `JPE` |
| American Economic Review | `AEREV` | `AER` |
| Quarterly Journal of Economics | `QJECO` | `QJE` |
| Econometrica | `ECON` | `ECA` |

`resolve_source("JPE")` 找不到 `JPECO`，所以查表失败。

### 问题 2：路径计算错误（已部分修复）

`Path(__file__).parent.parent.parent` 指向 `src/` 而非项目根目录。
已改为 `parent.parent.parent.parent`，但仍依赖模块加载方式。

### 问题 3：`resolve_source()` 仍有硬编码

当前实现中 `_MANUAL_JOURNAL_ALIASES` 和 `_BUILTIN_REPOS` 是函数内硬编码 dict。

---

## 解决方案

### Step 1：扩展 `journal_list.json`，加入 `short_name` 字段

每个期刊条目新增 `"short_name"` 字段，直接存储常用缩写：

```json
{
  "title": "Journal of Political Economy",
  "short_name": "JPE",
  "openalex_id": "S95323914",
  ...
},
{
  "title": "American Economic Review",
  "short_name": "AER",
  "openalex_id": "S23254222",
  ...
}
```

对于没有公认缩写的期刊，`short_name` 可省略。

### Step 2：修改 `_load_journal_aliases()` 加载 `short_name`

```python
# 同时存入 short_name（如果存在）和 _title_to_alias 生成的结果
if short_name := entry.get("short_name"):
    aliases[short_name]       = openalex_id
    aliases[short_name.upper()] = openalex_id
# 原有 _title_to_alias 结果也存入，作为后备
alias = _title_to_alias(title)
aliases[alias.upper()] = openalex_id
```

### Step 3：删除 `resolve_source()` 中的所有硬编码

删除 `_BUILTIN_REPOS` 和 `_MANUAL_JOURNAL_ALIASES`，解析链变为：

```
1. None / ""          → return None
2. "I{digits}"         → bare institution ID passthrough
3. "S{digits}"         → bare source ID passthrough
4. "SSRN"              → 从 working_paper_sources.json 查 ssrn_source_id
5. 其他 alias           → 先查 WP institutions（uppercase）
                         → 再查 journal aliases（uppercase）
                         → Unknown → ValueError
```

### Step 4：统一资产路径计算

在 `client.py` 开头用 `Path(__file__).resolve()` 计算项目根目录，消除路径层数猜测：

```python
import os as _os
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ASSETS       = _PROJECT_ROOT / "assets"
```

### Step 5：验证测试

```python
resolve_source("NBER")   → "I1321305853"
resolve_source("CEPR")   → "I4210140326"
resolve_source("SSRN")   → "S4210172589"
resolve_source("JPE")    → "S95323914"    # 来自 short_name
resolve_source("AER")    → "S23254222"    # 来自 short_name
resolve_source("QJE")    → "S203860005"    # 来自 short_name
resolve_source("S4210172589") → "S4210172589"  # passthrough
resolve_source("I1321305853") → "I1321305853"  # passthrough
resolve_source(None)     → None
build_source_filter("NBER") → "authorships.institutions.id:I1321305853"
build_source_filter("SSRN") → "primary_location.source.id:S4210172589"
```

### Step 6：端到端 API 测试

```python
search_works(["housing", "market"], source="NBER", per_page=2)
search_works(["fiscal", "policy"], source="JPE", per_page=2)
search_works(["carbon", "tax"], source=None, per_page=2)  # 全库
```

---

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `assets/journal_list.json` | 为所有主要期刊添加 `short_name` 字段 |
| `src/.../client.py` | Step 1–5 实现，删除所有硬编码 |
| `src/.../pipeline.py` | 更新 import（无功能变更） |
| `src/.../openclaw_runner.py` | 确认仍可正常调用 `search_works`（无功能变更） |
| `src/.../__init__.py` | 无变更 |

---

## 风险与待确认

1. **`journal_list.json` 需要用户手动补充 `short_name` 字段** — 是否可以接受？还是需要写一个脚本来自动从 OpenAlex API 补全？
2. **NBER 在 `working_paper_sources.json` 里是 institution ID（I 前缀），用于 `authorships.institutions.id` 过滤** — 这是正确的理解，请确认。
3. **SSRN 是 source ID（S 前缀），用于 `primary_location.source.id` 过滤** — 同上确认。
