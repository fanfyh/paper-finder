"""LLM-based paper relevance scoring using MiniMax API.

Scores each candidate paper against the user's 4 research interest directions
using semantic understanding (rather than keyword matching).
"""
from __future__ import annotations

import os
import logging
import requests
from typing import Any

LOG = logging.getLogger("llm_scorer")

# MiniMax domestic API (Anthropic-compatible)
MINIMAX_API_KEY = os.getenv("MINIMAX_DOMESTIC_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_DOMESTIC_BASE_URL", "https://api.minimaxi.com/anthropic")
MINIMAX_CHAT_MODEL = os.getenv("MINIMAX_CHAT_MODEL", "MiniMax-M2.7")


def _build_relevance_prompt(interests: list[dict], papers: list[dict]) -> tuple[str, str]:
    """Build system + user prompt for relevance scoring.

    Returns (system_prompt, user_prompt).
    """
    # Build interests description
    interest_lines = []
    for i, interest in enumerate(interests, 1):
        label = interest.get("label", interest.get("interest_id", "未知方向"))
        aliases = interest.get("query_aliases", [])
        methods = interest.get("method_keywords", [])
        desc = f"方向{i}: {label}"
        if aliases:
            desc += f"\n  检索词: {', '.join(aliases[:5])}"
        if methods:
            desc += f"\n  方法关键词: {', '.join(methods[:3])}"
        interest_lines.append(desc)

    interests_text = "\n\n".join(interest_lines)

    # Build papers list
    paper_lines = []
    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "无标题") or "无标题"
        abstract = paper.get("abstract", "")
        if isinstance(abstract, dict):
            # Inverted-index format — just use title only
            abstract = ""
        abstract = (abstract or "")[:500]
        paper_lines.append(f"论文{i}: {title}\n摘要: {abstract[:300]}")

    papers_text = "\n\n".join(paper_lines)

    system_prompt = """你是一位经济学学术助手。你的任务是对每篇论文评估其与用户研究兴趣的语义相关性。

用户有4个研究方向：
""" + interests_text + """

评分标准（0-10分）：
- 9-10分：高度相关，论文主题、方法或发现与用户研究方向直接相关
- 6-8分：相关，研究问题或工具有一定关联
- 3-5分：弱相关，需要仔细阅读才能发现联系
- 0-2分：不相关，主题偏离用户研究范围

输出格式：直接输出N行，每行一个分数，不要任何解释，不要编号/标题/分隔符。
格式：论文1:分数 论文2:分数 ...（每行一篇）
例如：论文1:8 论文2:3 论文3:0"""

    user_prompt = f"""请对以下{len(papers)}篇论文评分：\n\n{papers_text}"""

    return system_prompt, user_prompt


def score_papers_llm(
    papers: list[dict],
    interests: list[dict],
    *,
    batch_size: int = 10,
) -> dict[str, float]:
    """Score papers for relevance to research interests using MiniMax LLM.

    Args:
        papers: List of paper dicts with at least 'title' and 'abstract'.
        interests: List of research interest dicts from the profile.
        batch_size: Number of papers per LLM call (default 10).

    Returns:
        Dict mapping paper index (0-based int as string) to relevance score (0.0-1.0).
    """
    if not papers or not interests:
        return {}

    api_key = MINIMAX_API_KEY
    if not api_key:
        LOG.warning("MINIMAX_DOMESTIC_API_KEY not set, returning zero scores")
        return {str(i): 0.0 for i in range(len(papers))}

    all_scores: dict[str, float] = {}

    # Process in batches
    for batch_start in range(0, len(papers), batch_size):
        batch_end = min(batch_start + batch_size, len(papers))
        batch = papers[batch_start:batch_end]
        LOG.debug("Scoring batch %d-%d (%d papers)", batch_start + 1, batch_end, len(batch))

        batch_scores = _score_batch(batch, interests)
        # Re-index scores to global indices
        for local_idx, score in batch_scores.items():
            global_idx = str(int(local_idx) + batch_start)
            all_scores[global_idx] = score

        LOG.info("LLM scored %d/%d papers (batch %d-%d)",
                 len(all_scores), len(papers), batch_start + 1, batch_end)

    return all_scores


def _score_batch(papers: list[dict], interests: list[dict]) -> dict[str, float]:
    """Score a single batch of papers and return scores with local 0-based indices."""
    system_prompt, user_prompt = _build_relevance_prompt(interests, papers)

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": MINIMAX_CHAT_MODEL,
        "max_tokens": 512,
        "temperature": 0.1,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        response = requests.post(
            f"{MINIMAX_BASE_URL}/v1/messages",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()

        # Extract text from content blocks (MiniMax returns array with thinking + text)
        raw_text = ""
        content = result.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    raw_text = block.get("text", "").strip()
                    break
        if not raw_text:
            raw_text = str(result.get("content", ""))
    except Exception as exc:
        LOG.error("MiniMax API call failed: %s", exc)
        return {str(i): 0.0 for i in range(len(papers))}

    # Parse scores from LLM output
    # Expected format: "论文1:8 论文2:3 ..." or "论文1: 8\n论文2: 3\n..." (space after colon OK)
    scores: dict[str, float] = {}
    import re

    pattern = r"论文(\d+):\s*(\d+)"
    for match in re.finditer(pattern, raw_text):
        idx = int(match.group(1)) - 1  # 1-based → 0-based
        score = int(match.group(2))
        # Only accept scores within batch range
        if 0 <= idx < len(papers):
            scores[str(idx)] = max(0.0, min(10.0, score)) / 10.0  # Normalize to 0-1

    return scores


def add_llm_scores_to_candidates(
    candidates: list[dict],
    interests: list[dict],
) -> list[dict]:
    """Add LLM relevance scores to candidate list, updating _scores dict in-place.

    Returns the same candidates list with updated scores.
    """
    if not candidates:
        return candidates

    # Collect papers from candidates
    papers = []
    for c in candidates:
        paper_data = c.get("paper", {})
        title = paper_data.get("title") or c.get("title", "")
        abstract = paper_data.get("abstract_inverted_index") or paper_data.get("abstract") or c.get("abstract", "")
        papers.append({"title": title, "abstract": abstract})

    llm_scores = score_papers_llm(papers, interests)

    for i, candidate in enumerate(candidates):
        score = llm_scores.get(str(i), 0.0)
        existing = candidate.get("_scores", {})
        existing["llm_relevance"] = round(score, 4)
        existing["llm_model"] = os.getenv("MINIMAX_CHAT_MODEL", "MiniMax-Text-01")
        candidate["_scores"] = existing

    return candidates
