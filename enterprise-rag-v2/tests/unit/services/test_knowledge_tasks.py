from infrastructure.queue.knowledge_tasks import _tags


def test_knowledge_task_extracts_deduplicated_tags():
    assert _tags("人工智能 AI platform 人工智能") == ["人工智能", "platform"]
