from infrastructure.database.models import Asset, AssetSourceType, AssetStatus, Base


def test_asset_model_is_tenant_scoped_and_compatible_with_documents():
    table = Base.metadata.tables["assets"]

    assert Asset.__tablename__ == "assets"
    assert {"tenant_id", "workspace_id", "created_by"}.issubset(table.columns.keys())
    assert "legacy_document_id" in table.columns
    assert table.c.legacy_document_id.unique is True
    assert AssetSourceType.URL.value == "url"
    assert AssetStatus.READY.value == "ready"


def test_asset_metadata_does_not_store_source_body_by_default():
    asset = Asset(title="Industry brief", source_type=AssetSourceType.URL.value)

    assert asset.extra_metadata is None or asset.extra_metadata == {}
    assert asset.deleted_at is None
    assert asset.status in (None, AssetStatus.PENDING.value)
