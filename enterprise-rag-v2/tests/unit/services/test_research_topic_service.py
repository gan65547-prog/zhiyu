from types import SimpleNamespace

from services.impl.research_topic_service import ResearchTopicService


def test_topic_clusters_count_each_topic_once_per_source():
    sources = [
        (SimpleNamespace(id="source-1"), "智能制造 质量控制 质量控制"),
        (SimpleNamespace(id="source-2"), "智能制造 供应链管理"),
    ]
    clusters = ResearchTopicService.cluster(sources)
    by_topic = {item["topic"]: item for item in clusters}
    assert by_topic["智能制造"]["source_count"] == 2
    assert by_topic["质量控制"]["source_count"] == 1
    assert by_topic["质量控制"]["source_ids"] == ["source-1"]
