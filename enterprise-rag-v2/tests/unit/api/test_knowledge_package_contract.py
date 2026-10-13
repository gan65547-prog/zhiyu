from datetime import datetime, timezone

from api.schemas.asset import KnowledgePackageImportRequest


def _request(**overrides):
    payload = {
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "package_id": "edge-case-2026-001",
        "title": "固定区域入侵检测 POC",
        "source_system": "external-edge-ai",
        "source_version": "abc123",
        "provided_by": "authorized-owner",
        "licensed_scope": "internal-research",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "claims": [{"text": "固定摄像头下输出区域进入事件", "evidence_refs": ["ev-001"]}],
        "limits": ["不代表多路摄像头长稳"],
    }
    payload.update(overrides)
    return KnowledgePackageImportRequest.model_validate(payload)


def test_verified_package_is_allowed_to_seed_formal_knowledge():
    metadata = _request().as_asset_metadata()

    assert metadata["governance"] == {
        "verification_status": "verified",
        "issues": [],
        "can_seed_formal_knowledge": True,
    }


def test_incomplete_package_is_preserved_as_unverified_material():
    metadata = _request(source_version=None, limits=[]).as_asset_metadata()

    assert metadata["governance"]["verification_status"] == "unverified"
    assert metadata["governance"]["can_seed_formal_knowledge"] is False
    assert "缺少 source_version" in metadata["governance"]["issues"]
    assert "至少需要一条 limits" in metadata["governance"]["issues"]
