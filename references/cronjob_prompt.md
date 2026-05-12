## 任务：每周论文 digest（每周二 09:00 执行）

### 第一步：运行 digest

```bash
cd ~/.claude/tools/paper-finder && \
uv run --project . paper-finder \
  --action digest-all \
  --config ~/.claude/tools/paper-finder/config.json
```

### 第二步：判断是否有结果

- 如果输出包含"No new papers"，回复：`✅ 本周未发现新的相关论文。`
- 如果有论文结果，进入第三步。

### 第三步：确认报告

运行后 HTML 报告会生成在 `~/.claude/tools/paper-finder/reports/` 目录（文件名含当天日期）。

### 第四步：回复用户

最终回复格式：
```
📚 论文周报 | YYYY-MM-DD（周X）

共发现 **N** 篇相关论文
[简要列表：标题 + 一句话推荐理由]
完整报告：~/.claude/tools/paper-finder/reports/YYYY-MM-DD.html
```

**注意**：最终回复只输出消息文本，不要输出其他说明。
