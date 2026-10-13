"""研究来源的可解释主题聚类；不调用模型，不改变证据边界。"""

import re
from collections import Counter, defaultdict
from typing import Any


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z][a-zA-Z0-9_-]{2,}")
_STOPWORDS = {
    "我们", "你们", "他们", "以及", "因为", "所以", "如果", "这个", "那个", "进行", "可以",
    "需要", "相关", "通过", "目前", "以及", "there", "these", "those", "with", "from",
}


class ResearchTopicService:
    """按来源去重计数，输出主题及其覆盖来源数，便于审核和后续模型综合。"""

    @staticmethod
    def cluster(source_pairs: list[tuple[Any, str]], limit: int = 8) -> list[dict[str, Any]]:
        source_counts: Counter[str] = Counter()
        source_ids: defaultdict[str, set[str]] = defaultdict(set)
        for source, content in source_pairs:
            source_id = str(getattr(source, "id", ""))
            tokens = {
                token.lower() for token in _TOKEN_PATTERN.findall(content or "")
                if token.lower() not in _STOPWORDS
            }
            for token in tokens:
                source_counts[token] += 1
                source_ids[token].add(source_id)
        return [
            {"topic": topic, "source_count": count, "source_ids": sorted(source_ids[topic])}
            for topic, count in source_counts.most_common(limit)
        ]
