"""Consolidate orphan branches into single linear head

Revision ID: 013_merge_branches
Revises: 012_widen_alembic_version_num
Create Date: 2026-04-20

After consolidating orphan branches, the migration chain is now linear:
  - 011_audit_logs_align_orm (main chain)
  - 011_fix_opsquotadimension_enum (now sequential after audit logs)
  - 012_widen_alembic_version_num
  - 013_merge_branches (final consolidation point)

All migrations are now in a single linear sequence with full idempotency support.
"""

from alembic import op

revision = "013_merge_branches"
down_revision = "012_widen_alembic_version_num"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema changes - this is purely a consolidation point
    pass


def downgrade() -> None:
    pass
