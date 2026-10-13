"""add learning diagnosis tables

Revision ID: 022_add_learning_diagnosis_tables
Revises: 021_add_work_orders_and_instances
Create Date: 2026-05-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '022_add_learning_diagnosis_tables'
down_revision: Union[str, None] = '022_add_xlsx_csv_document_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    uuid_type = sa.String(36) if is_sqlite else postgresql.UUID(as_uuid=True)
    json_type = sa.JSON() if is_sqlite else postgresql.JSONB()
    json_list_default = sa.text("'[]'") if is_sqlite else sa.text("'[]'::jsonb")
    json_object_default = sa.text("'{}'") if is_sqlite else sa.text("'{}'::jsonb")
    inspector = sa.inspect(bind)
    expected_tables = {
        'learning_subjects',
        'learning_textbook_versions',
        'learning_knowledge_points',
        'learning_materials',
        'learning_diagnosis_reports',
        'learning_practice_sessions',
        'learning_student_profiles',
        'learning_error_records',
    }

    # Some staging databases received these tables before Alembic recorded this
    # revision. Treat that state as already migrated so container startup can
    # continue and Alembic can advance the version marker.
    existing_tables = set(inspector.get_table_names())
    if expected_tables.issubset(existing_tables):
        return
    if expected_tables & existing_tables:
        existing_learning_tables = ', '.join(sorted(expected_tables & existing_tables))
        raise RuntimeError(
            'Partial learning diagnosis migration state detected. '
            f'Existing tables: {existing_learning_tables}'
        )

    op.create_table(
        'learning_subjects',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('grade_level', sa.String(20), nullable=False),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_subject_name', 'learning_subjects', ['name'])
    op.create_index('idx_learning_subject_grade', 'learning_subjects', ['grade_level'])

    op.create_table(
        'learning_textbook_versions',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('subject_id', uuid_type,
                  sa.ForeignKey('learning_subjects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('publisher', sa.String(100), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('semester', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_tv_subject', 'learning_textbook_versions', ['subject_id'])
    op.create_index('idx_learning_tv_grade', 'learning_textbook_versions', ['grade'])
    if bind.dialect.name == 'sqlite':
        # SQLite cannot add a table-level constraint through ALTER TABLE.
        # A unique index preserves the same invariant without requiring a
        # table rebuild, which is important for the local/test database path.
        op.create_index(
            'uq_learning_tv', 'learning_textbook_versions',
            ['subject_id', 'publisher', 'grade', 'semester'], unique=True
        )
    else:
        op.create_unique_constraint('uq_learning_tv', 'learning_textbook_versions',
                                    ['subject_id', 'publisher', 'grade', 'semester'])

    op.create_table(
        'learning_knowledge_points',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('subject_id', uuid_type,
                  sa.ForeignKey('learning_subjects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('textbook_version_id', uuid_type,
                  sa.ForeignKey('learning_textbook_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('parent_id', uuid_type,
                  sa.ForeignKey('learning_knowledge_points.id', ondelete='SET NULL'), nullable=True),
        sa.Column('chapter', sa.String(200), nullable=True),
        sa.Column('page_range', sa.String(50), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('prerequisite_kp_ids', json_type, default=json_list_default),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('metadata', json_type, default=json_object_default),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_kp_subject', 'learning_knowledge_points', ['subject_id'])
    op.create_index('idx_learning_kp_tv', 'learning_knowledge_points', ['textbook_version_id'])
    op.create_index('idx_learning_kp_parent', 'learning_knowledge_points', ['parent_id'])
    op.create_index('idx_learning_kp_code', 'learning_knowledge_points', ['code'])
    op.create_index('idx_learning_kp_difficulty', 'learning_knowledge_points', ['difficulty_level'])

    op.create_table(
        'learning_materials',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('knowledge_point_id', uuid_type,
                  sa.ForeignKey('learning_knowledge_points.id', ondelete='CASCADE'), nullable=False),
        sa.Column('textbook_version_id', uuid_type,
                  sa.ForeignKey('learning_textbook_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(300), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('vector_id', sa.String(200), nullable=True),
        sa.Column('chunk_index', sa.Integer(), default=0),
        sa.Column('metadata', json_type, default=json_object_default),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_mat_kp', 'learning_materials', ['knowledge_point_id'])
    op.create_index('idx_learning_mat_tv', 'learning_materials', ['textbook_version_id'])
    op.create_index('idx_learning_mat_type', 'learning_materials', ['content_type'])
    op.create_index('idx_learning_mat_vector', 'learning_materials', ['vector_id'])

    op.create_table(
        'learning_diagnosis_reports',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('user_id', uuid_type,
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject_id', uuid_type,
                  sa.ForeignKey('learning_subjects.id', ondelete='SET NULL'), nullable=False),
        sa.Column('textbook_version_id', uuid_type,
                  sa.ForeignKey('learning_textbook_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('grade_level', sa.String(20), nullable=True),
        sa.Column('input_type', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('original_images', json_type, default=json_list_default),
        sa.Column('original_answer', sa.Text(), nullable=True),
        sa.Column('kp_code', sa.String(50), nullable=True),
        sa.Column('error_tags', json_type, default=json_list_default),
        sa.Column('weak_knowledge_points', json_type, default=json_list_default),
        sa.Column('error_analysis', json_type, default=json_list_default),
        sa.Column('overall_mastery_score', sa.Integer(), nullable=True),
        sa.Column('stage_results', json_type, default=json_object_default),
        sa.Column('report_content', json_type, default=json_object_default),
        sa.Column('practice_session_id', uuid_type, nullable=True),
        sa.Column('rating', sa.String(20), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='completed'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_report_user', 'learning_diagnosis_reports', ['user_id'])
    op.create_index('idx_learning_report_subject', 'learning_diagnosis_reports', ['subject_id'])
    op.create_index('idx_learning_report_status', 'learning_diagnosis_reports', ['status'])
    op.create_index('idx_learning_report_created', 'learning_diagnosis_reports', ['created_at'])
    op.create_index('idx_learning_report_user_subject', 'learning_diagnosis_reports', ['user_id', 'subject_id'])

    op.create_table(
        'learning_practice_sessions',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('diagnosis_report_id', uuid_type,
                  sa.ForeignKey('learning_diagnosis_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', uuid_type,
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('knowledge_point_ids', json_type, default=json_list_default),
        sa.Column('exercises', json_type, default=json_list_default),
        sa.Column('answers_submitted', json_type, default=json_list_default),
        sa.Column('exercises_completed', sa.Integer(), default=0),
        sa.Column('exercises_correct', sa.Integer(), default=0),
        sa.Column('mastery_before', sa.Integer(), nullable=True),
        sa.Column('mastery_after', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), server_default='generated'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_ps_report', 'learning_practice_sessions', ['diagnosis_report_id'])
    op.create_index('idx_learning_ps_user', 'learning_practice_sessions', ['user_id'])
    op.create_index('idx_learning_ps_status', 'learning_practice_sessions', ['status'])
    op.create_index('idx_learning_ps_created', 'learning_practice_sessions', ['created_at'])

    if bind.dialect.name != 'sqlite':
        op.create_foreign_key(
            'fk_learning_report_practice',
            'learning_diagnosis_reports', 'learning_practice_sessions',
            ['practice_session_id'], ['id'], ondelete='SET NULL'
        )

    op.create_table(
        'learning_student_profiles',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('user_id', uuid_type,
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('grade_level', sa.String(20), nullable=True),
        sa.Column('subjects', json_type, default=json_list_default),
        sa.Column('knowledge_mastery', json_type, default=json_object_default),
        sa.Column('total_diagnoses', sa.Integer(), default=0),
        sa.Column('total_practice_sessions', sa.Integer(), default=0),
        sa.Column('avg_mastery_score', sa.Integer(), nullable=True),
        sa.Column('metadata', json_type, default=json_object_default),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_profile_user', 'learning_student_profiles', ['user_id'], unique=True)
    op.create_index('idx_learning_profile_grade', 'learning_student_profiles', ['grade_level'])

    op.create_table(
        'learning_error_records',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('knowledge_point_id', uuid_type,
                  sa.ForeignKey('learning_knowledge_points.id', ondelete='CASCADE'), nullable=False),
        sa.Column('error_type', sa.String(100), nullable=False),
        sa.Column('error_description', sa.Text(), nullable=False),
        sa.Column('correct_approach', sa.Text(), nullable=True),
        sa.Column('frequency', sa.Integer(), default=1),
        sa.Column('metadata', json_type, default=json_object_default),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_learning_err_kp', 'learning_error_records', ['knowledge_point_id'])
    op.create_index('idx_learning_err_type', 'learning_error_records', ['error_type'])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table('learning_error_records')
    op.drop_table('learning_student_profiles')
    if bind.dialect.name == 'sqlite':
        op.drop_index('uq_learning_tv', table_name='learning_textbook_versions')
    else:
        op.execute('ALTER TABLE learning_diagnosis_reports DROP CONSTRAINT IF EXISTS fk_learning_report_practice')
    op.drop_table('learning_practice_sessions')
    op.drop_table('learning_diagnosis_reports')
    op.drop_table('learning_materials')
    op.drop_table('learning_knowledge_points')
    op.drop_table('learning_textbook_versions')
    op.drop_table('learning_subjects')
