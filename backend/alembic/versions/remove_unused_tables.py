"""Remove unused tables: 3D datasets, annotations, benchmarks

Revision ID: remove_unused_tables
Revises:
Create Date: 2025-10-09 00:00:00.000000

This migration removes tables that are not used by the frontend:
- 3D dataset tables (datasets_3d, images_3d, patches_3d, attack_datasets_3d)
- Annotations table
- Model benchmarks table
- Related views and indexes
- Related ENUM types for 3D patches and annotations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'remove_unused_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unused tables and related database objects"""

    # Drop materialized views and views that reference the tables to be dropped
    op.execute("DROP MATERIALIZED VIEW IF EXISTS experiment_summary CASCADE")
    op.execute("DROP VIEW IF EXISTS image_annotation_summary CASCADE")
    op.execute("DROP VIEW IF EXISTS model_benchmark_comparison CASCADE")

    # Drop indexes explicitly (for safety, though CASCADE should handle it)
    # Annotations indexes
    op.execute("DROP INDEX IF EXISTS idx_annotations_image_2d")
    op.execute("DROP INDEX IF EXISTS idx_annotations_image_3d")
    op.execute("DROP INDEX IF EXISTS idx_annotations_class")
    op.execute("DROP INDEX IF EXISTS idx_annotations_class_idx")
    op.execute("DROP INDEX IF EXISTS idx_annotations_type")
    op.execute("DROP INDEX IF EXISTS idx_annotations_active_2d")
    op.execute("DROP INDEX IF EXISTS idx_annotations_active_3d")
    op.execute("DROP INDEX IF EXISTS idx_annotations_polygon_gin")
    op.execute("DROP INDEX IF EXISTS idx_annotations_keypoints_gin")

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS annotations_calculate_area_trg ON annotations")
    op.execute("DROP FUNCTION IF EXISTS trg_calculate_annotation_area()")

    # Drop tables in correct order (respecting foreign key constraints)
    # 1. Drop annotations table
    op.drop_table('annotations')

    # 2. Drop model_benchmarks table
    op.drop_table('model_benchmarks')

    # 3. Drop 3D attack datasets (depends on patches_3d and datasets_3d)
    op.execute("ALTER TABLE attack_datasets_3d DROP CONSTRAINT IF EXISTS fk_attack_3d_experiment")
    op.drop_table('attack_datasets_3d')

    # 4. Drop 3D patches (depends on datasets_3d)
    op.drop_table('patches_3d')

    # 5. Drop 3D images (depends on datasets_3d)
    op.drop_table('images_3d')

    # 6. Drop 3D datasets
    op.drop_table('datasets_3d')

    # Drop ENUM types that are no longer needed
    op.execute("DROP TYPE IF EXISTS annotation_type_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS patch3d_method_enum CASCADE")

    # Update eval_runs table to remove 3D-related columns
    op.execute("ALTER TABLE eval_runs DROP COLUMN IF EXISTS base_dataset_3d_id")
    op.execute("ALTER TABLE eval_runs DROP COLUMN IF EXISTS attack_dataset_3d_id")
    op.execute("ALTER TABLE eval_runs DROP COLUMN IF EXISTS dataset_dimension")

    # Update eval_items table to remove 3D image reference
    op.execute("ALTER TABLE eval_items DROP COLUMN IF EXISTS image_3d_id")

    # Drop indexes related to removed columns
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_dimension")
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_base_3d")
    op.execute("DROP INDEX IF EXISTS idx_eval_runs_attack_3d")
    op.execute("DROP INDEX IF EXISTS idx_eval_items_image_3d")

    # Drop dataset_dimension_enum if no other tables use it
    op.execute("DROP TYPE IF EXISTS dataset_dimension_enum CASCADE")

    # Recreate experiment_summary materialized view without 3D references
    op.execute("""
        CREATE MATERIALIZED VIEW experiment_summary AS
        SELECT
          e.id,
          e.name,
          e.status,
          e.started_at,
          e.ended_at,
          COUNT(DISTINCT a2d.id) AS attack_2d_count,
          COUNT(DISTINCT er.id) AS eval_run_count,
          e.created_at,
          e.created_by
        FROM experiments e
        LEFT JOIN attack_datasets_2d a2d ON e.id = a2d.experiment_id AND a2d.deleted_at IS NULL
        LEFT JOIN eval_runs er ON e.id = er.experiment_id AND er.deleted_at IS NULL
        WHERE e.deleted_at IS NULL
        GROUP BY e.id, e.name, e.status, e.started_at, e.ended_at, e.created_at, e.created_by
    """)

    op.execute("CREATE UNIQUE INDEX idx_experiment_summary_id ON experiment_summary(id)")

    # Simplify eval_runs check constraint (remove 3D-related logic)
    op.execute("ALTER TABLE eval_runs DROP CONSTRAINT IF EXISTS chk_eval_phase_requirements")
    op.execute("""
        ALTER TABLE eval_runs ADD CONSTRAINT chk_eval_phase_requirements CHECK (
            (phase = 'pre_attack' AND base_dataset_id IS NOT NULL AND attack_dataset_id IS NULL)
            OR
            (phase = 'post_attack' AND attack_dataset_id IS NOT NULL)
        )
    """)


def downgrade() -> None:
    """Recreate the removed tables and database objects"""

    # Recreate ENUM types
    op.execute("CREATE TYPE annotation_type_enum AS ENUM ('bbox', 'polygon', 'keypoint', 'segmentation')")
    op.execute("CREATE TYPE patch3d_method_enum AS ENUM ('texture', 'material', 'uv', 'sticker', 'custom')")
    op.execute("CREATE TYPE dataset_dimension_enum AS ENUM ('2d', '3d')")

    # Recreate datasets_3d table
    op.execute("""
        CREATE TABLE datasets_3d (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name varchar(200) NOT NULL,
          description text,
          owner_id uuid REFERENCES users(id) ON DELETE SET NULL,
          carla_environment jsonb NULL,
          object_models jsonb NULL,
          image_resolution jsonb NULL,
          storage_path text NOT NULL,
          metadata jsonb NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz NULL,
          CONSTRAINT chk_datasets_3d_name CHECK (char_length(name) > 0),
          CONSTRAINT chk_image_resolution_json CHECK (image_resolution IS NULL OR jsonb_typeof(image_resolution) = 'object'),
          CONSTRAINT chk_carla_environment_json CHECK (carla_environment IS NULL OR jsonb_typeof(carla_environment) = 'object'),
          CONSTRAINT chk_object_models_json CHECK (object_models IS NULL OR jsonb_typeof(object_models) = 'array'),
          CONSTRAINT chk_metadata_json CHECK (metadata IS NULL OR jsonb_typeof(metadata) = 'object')
        )
    """)

    # Recreate images_3d table
    op.execute("""
        CREATE TABLE images_3d (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          dataset_id uuid NOT NULL REFERENCES datasets_3d(id) ON DELETE CASCADE,
          file_name varchar(1024) NOT NULL,
          storage_key text NOT NULL,
          width integer NULL,
          height integer NULL,
          mime_type varchar(100) NULL,
          camera_position jsonb NULL,
          camera_rotation jsonb NULL,
          scene_metadata jsonb NULL,
          metadata jsonb NULL,
          uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz NULL,
          CONSTRAINT chk_images_3d_dimensions CHECK ((width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)),
          CONSTRAINT chk_images_3d_file_name CHECK (char_length(file_name) > 0)
        )
    """)

    # Recreate patches_3d table
    op.execute("""
        CREATE TABLE patches_3d (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name varchar(200) NOT NULL,
          description text,
          source_dataset_id uuid REFERENCES datasets_3d(id) ON DELETE SET NULL,
          target_model_version_id uuid REFERENCES od_model_versions(id) ON DELETE RESTRICT,
          target_class varchar(200) NULL,
          method patch3d_method_enum NOT NULL DEFAULT 'texture',
          hyperparameters jsonb NULL,
          patch_metadata jsonb NULL,
          storage_key text,
          file_name varchar(1024),
          size_bytes bigint,
          sha256 char(64),
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz NULL,
          CONSTRAINT chk_patches_3d_name CHECK (char_length(name) > 0)
        )
    """)

    # Recreate attack_datasets_3d table
    op.execute("""
        CREATE TABLE attack_datasets_3d (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name varchar(200) NOT NULL,
          description text,
          base_dataset_id uuid NOT NULL REFERENCES datasets_3d(id) ON DELETE RESTRICT,
          attack_patch_id uuid NOT NULL REFERENCES patches_3d(id) ON DELETE RESTRICT,
          target_model_version_id uuid REFERENCES od_model_versions(id) ON DELETE RESTRICT,
          parameters jsonb NULL,
          placement jsonb GENERATED ALWAYS AS (parameters->'placement') STORED,
          experiment_id uuid REFERENCES experiments(id) ON DELETE SET NULL,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz NULL,
          CONSTRAINT chk_attack_3d_name CHECK (char_length(name) > 0)
        )
    """)

    # Recreate annotations table
    op.execute("""
        CREATE TABLE annotations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          image_2d_id uuid REFERENCES images_2d(id) ON DELETE CASCADE,
          image_3d_id uuid REFERENCES images_3d(id) ON DELETE CASCADE,
          annotation_type annotation_type_enum NOT NULL DEFAULT 'bbox',
          class_name varchar(200) NOT NULL,
          class_index integer,
          bbox_x numeric(10,2),
          bbox_y numeric(10,2),
          bbox_width numeric(10,2),
          bbox_height numeric(10,2),
          polygon_data jsonb,
          keypoints jsonb,
          confidence numeric(5,4) DEFAULT 1.0,
          is_crowd boolean DEFAULT false,
          area numeric(12,2),
          metadata jsonb,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz NULL,
          CONSTRAINT chk_annotation_image_xor CHECK (
            (image_2d_id IS NOT NULL AND image_3d_id IS NULL) OR
            (image_2d_id IS NULL AND image_3d_id IS NOT NULL)
          )
        )
    """)

    # Recreate model_benchmarks table
    op.execute("""
        CREATE TABLE model_benchmarks (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE CASCADE,
          dataset_2d_id uuid REFERENCES datasets_2d(id) ON DELETE CASCADE,
          dataset_3d_id uuid REFERENCES datasets_3d(id) ON DELETE CASCADE,
          benchmark_type varchar(100) NOT NULL,
          metrics jsonb NOT NULL,
          test_config jsonb,
          evaluated_at timestamptz NOT NULL DEFAULT now(),
          notes text,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deleted_at timestamptz NULL,
          CONSTRAINT chk_benchmark_dataset CHECK (
            (dataset_2d_id IS NOT NULL AND dataset_3d_id IS NULL) OR
            (dataset_2d_id IS NULL AND dataset_3d_id IS NOT NULL)
          )
        )
    """)

    # Add back 3D columns to eval_runs
    op.execute("ALTER TABLE eval_runs ADD COLUMN dataset_dimension dataset_dimension_enum NOT NULL DEFAULT '2d'")
    op.execute("ALTER TABLE eval_runs ADD COLUMN base_dataset_3d_id uuid REFERENCES datasets_3d(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE eval_runs ADD COLUMN attack_dataset_3d_id uuid REFERENCES attack_datasets_3d(id) ON DELETE RESTRICT")

    # Add back 3D column to eval_items
    op.execute("ALTER TABLE eval_items ADD COLUMN image_3d_id uuid REFERENCES images_3d(id) ON DELETE SET NULL")

    # Restore complex eval_runs check constraint
    op.execute("ALTER TABLE eval_runs DROP CONSTRAINT IF EXISTS chk_eval_phase_requirements")
    op.execute("""
        ALTER TABLE eval_runs ADD CONSTRAINT chk_eval_phase_requirements CHECK (
            (dataset_dimension = '2d' AND phase = 'pre_attack' AND base_dataset_id IS NOT NULL
             AND attack_dataset_id IS NULL AND base_dataset_3d_id IS NULL AND attack_dataset_3d_id IS NULL)
            OR
            (dataset_dimension = '2d' AND phase = 'post_attack' AND attack_dataset_id IS NOT NULL
             AND base_dataset_3d_id IS NULL AND attack_dataset_3d_id IS NULL)
            OR
            (dataset_dimension = '3d' AND phase = 'pre_attack' AND base_dataset_3d_id IS NOT NULL
             AND attack_dataset_3d_id IS NULL AND base_dataset_id IS NULL AND attack_dataset_id IS NULL)
            OR
            (dataset_dimension = '3d' AND phase = 'post_attack' AND attack_dataset_3d_id IS NOT NULL
             AND base_dataset_id IS NULL AND attack_dataset_id IS NULL)
        )
    """)

    # Recreate views with 3D references
    op.execute("DROP MATERIALIZED VIEW IF EXISTS experiment_summary")
    op.execute("""
        CREATE MATERIALIZED VIEW experiment_summary AS
        SELECT
          e.id,
          e.name,
          e.status,
          e.started_at,
          e.ended_at,
          COUNT(DISTINCT a2d.id) AS attack_2d_count,
          COUNT(DISTINCT a3d.id) AS attack_3d_count,
          COUNT(DISTINCT er.id) AS eval_run_count,
          e.created_at,
          e.created_by
        FROM experiments e
        LEFT JOIN attack_datasets_2d a2d ON e.id = a2d.experiment_id AND a2d.deleted_at IS NULL
        LEFT JOIN attack_datasets_3d a3d ON e.id = a3d.experiment_id AND a3d.deleted_at IS NULL
        LEFT JOIN eval_runs er ON e.id = er.experiment_id AND er.deleted_at IS NULL
        WHERE e.deleted_at IS NULL
        GROUP BY e.id, e.name, e.status, e.started_at, e.ended_at, e.created_at, e.created_by
    """)

    op.execute("CREATE UNIQUE INDEX idx_experiment_summary_id ON experiment_summary(id)")

    # Recreate annotation and benchmark views
    op.execute("""
        CREATE OR REPLACE VIEW image_annotation_summary AS
        SELECT
          '2d' AS dimension,
          i.id AS image_id,
          i.file_name,
          i.dataset_id,
          COUNT(a.id) AS annotation_count,
          COUNT(DISTINCT a.class_name) AS unique_classes,
          jsonb_agg(DISTINCT a.class_name ORDER BY a.class_name) AS classes
        FROM images_2d i
        LEFT JOIN annotations a ON i.id = a.image_2d_id AND a.deleted_at IS NULL
        WHERE i.deleted_at IS NULL
        GROUP BY i.id, i.file_name, i.dataset_id
        UNION ALL
        SELECT
          '3d' AS dimension,
          i.id AS image_id,
          i.file_name,
          i.dataset_id,
          COUNT(a.id) AS annotation_count,
          COUNT(DISTINCT a.class_name) AS unique_classes,
          jsonb_agg(DISTINCT a.class_name ORDER BY a.class_name) AS classes
        FROM images_3d i
        LEFT JOIN annotations a ON i.id = a.image_3d_id AND a.deleted_at IS NULL
        WHERE i.deleted_at IS NULL
        GROUP BY i.id, i.file_name, i.dataset_id
    """)

    op.execute("""
        CREATE OR REPLACE VIEW model_benchmark_comparison AS
        SELECT
          m.name AS model_name,
          mv.version,
          mv.framework,
          COALESCE(d2d.name, d3d.name) AS dataset_name,
          CASE WHEN mb.dataset_2d_id IS NOT NULL THEN '2d' ELSE '3d' END AS dimension,
          mb.benchmark_type,
          mb.metrics,
          mb.evaluated_at
        FROM model_benchmarks mb
        JOIN od_model_versions mv ON mb.model_version_id = mv.id
        JOIN od_models m ON mv.model_id = m.id
        LEFT JOIN datasets_2d d2d ON mb.dataset_2d_id = d2d.id
        LEFT JOIN datasets_3d d3d ON mb.dataset_3d_id = d3d.id
        WHERE mb.deleted_at IS NULL
        ORDER BY m.name, mv.version, mb.evaluated_at DESC
    """)
