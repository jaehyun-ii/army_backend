-- =====================================================================
-- Adversarial Vision Platform - Complete PostgreSQL Schema
-- Combines:
--   1. Integrated Schema (4 original schemas)
--   2. Schema Improvements (3D evaluation, annotations, experiments, etc.)
-- PostgreSQL >= 13
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- =========================
-- ENUM TYPES
-- =========================

-- User roles
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
    CREATE TYPE user_role_enum AS ENUM ('user', 'admin');
  END IF;
END $$;

-- 2D Attack types
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attack_type_enum') THEN
    CREATE TYPE attack_type_enum AS ENUM ('patch', 'noise');
  END IF;
END $$;

-- 3D Patch methods
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'patch3d_method_enum') THEN
    CREATE TYPE patch3d_method_enum AS ENUM (
      'texture',     -- adversarial texture mapping
      'material',    -- material/shader parameter perturbation
      'uv',          -- UV-space perturbation
      'sticker',     -- decal/sticker style patch
      'custom'       -- fallback/experimental
    );
  END IF;
END $$;

-- Real-time capture run status
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rt_run_status_enum') THEN
    CREATE TYPE rt_run_status_enum AS ENUM ('running','completed','failed','aborted');
  END IF;
END $$;

-- Model framework
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'model_framework_enum') THEN
    CREATE TYPE model_framework_enum AS ENUM ('pytorch','tensorflow','onnx','tensorrt','openvino','custom');
  END IF;
END $$;

-- Model stage
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'model_stage_enum') THEN
    CREATE TYPE model_stage_enum AS ENUM ('draft','staging','production','archived');
  END IF;
END $$;

-- Artifact types
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'artifact_type_enum') THEN
    CREATE TYPE artifact_type_enum AS ENUM (
      'model',        -- core model file (e.g., .pt, .onnx)
      'weights',      -- weights blob if separate
      'config',       -- model config, pipeline yaml/json, hyperparams
      'labelmap',     -- label mapping file (txt/json)
      'tokenizer',    -- if applicable
      'calibration',  -- INT8 calibration data
      'support',      -- misc support files (plugins, custom ops)
      'other'
    );
  END IF;
END $$;

-- Evaluation status
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eval_status_enum') THEN
    CREATE TYPE eval_status_enum AS ENUM ('queued','running','completed','failed','aborted');
  END IF;
END $$;

-- Evaluation phase
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eval_phase_enum') THEN
    CREATE TYPE eval_phase_enum AS ENUM ('pre_attack','post_attack');
  END IF;
END $$;

-- Dataset dimension (NEW: from improvements)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dataset_dimension_enum') THEN
    CREATE TYPE dataset_dimension_enum AS ENUM ('2d', '3d');
  END IF;
END $$;

-- Annotation type (NEW: from improvements)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'annotation_type_enum') THEN
    CREATE TYPE annotation_type_enum AS ENUM ('bbox', 'polygon', 'keypoint', 'segmentation');
  END IF;
END $$;

-- Experiment status (NEW: from improvements)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'experiment_status_enum') THEN
    CREATE TYPE experiment_status_enum AS ENUM ('draft','running','completed','failed','archived');
  END IF;
END $$;

-- =========================
-- HELPER FUNCTIONS
-- =========================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- Validate real-time capture run completion (soft validation to prevent race conditions)
CREATE OR REPLACE FUNCTION trg_validate_run_completion()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  frame_cnt integer;
BEGIN
  IF (TG_OP = 'UPDATE' AND NEW.status = 'completed' AND (OLD.status IS DISTINCT FROM NEW.status)) THEN
    SELECT count(*) INTO frame_cnt FROM rt_frames WHERE run_id = NEW.id AND deleted_at IS NULL;
    IF frame_cnt <> NEW.frames_expected THEN
      -- Soft validation: preserve original status and add diagnostic note
      -- This allows for manual review or automated retry rather than forcing failure
      NEW.status := OLD.status;  -- Keep original status (typically 'running')
      NEW.notes := coalesce(NEW.notes, '') ||
        format(' | [WARN] Completion blocked: frame_count=%s expected=%s. Review and retry completion. (at %s)',
               frame_cnt, NEW.frames_expected, now());
      RETURN NEW;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

-- =========================
-- CORE TABLES
-- =========================

-- ========== USERS ==========
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email varchar(320) NOT NULL,
  password_hash varchar(255) NOT NULL,  -- bcrypt: 60 chars, argon2: ~100 chars, 255 is safe
  display_name varchar(200),
  role user_role_enum NOT NULL DEFAULT 'user',
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_users_email CHECK (position('@' in email) > 1)
);
-- Case-insensitive unique email (prevents user@example.com and USER@EXAMPLE.COM duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
  ON users ((lower(email))) WHERE deleted_at IS NULL;

-- ========== MODEL REPOSITORY TABLES ==========

-- ========== OD_MODELS (Model catalog) ==========
CREATE TABLE IF NOT EXISTS od_models (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  task varchar(50) NOT NULL DEFAULT 'object-detection',
  owner_id uuid REFERENCES users(id) ON DELETE SET NULL,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_od_models_task CHECK (char_length(task) > 0)
);
CREATE INDEX IF NOT EXISTS idx_od_models_owner ON od_models(owner_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_od_models_name_active
  ON od_models (name) WHERE deleted_at IS NULL;

-- ========== OD_MODEL_VERSIONS ==========
CREATE TABLE IF NOT EXISTS od_model_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id uuid NOT NULL REFERENCES od_models(id) ON DELETE CASCADE,
  version varchar(64) NOT NULL,
  framework model_framework_enum NOT NULL,
  framework_version varchar(64),
  input_spec jsonb,
  training_metadata jsonb,
  labelmap jsonb,
  inference_params jsonb,
  stage model_stage_enum NOT NULL DEFAULT 'draft',
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz NULL,
  deleted_at timestamptz NULL,
  CONSTRAINT uq_model_version UNIQUE (model_id, version),
  CONSTRAINT chk_input_spec CHECK (input_spec IS NULL OR jsonb_typeof(input_spec)='object'),
  CONSTRAINT chk_labelmap CHECK (labelmap IS NULL OR jsonb_typeof(labelmap)='object'),
  CONSTRAINT chk_inference_params CHECK (inference_params IS NULL OR jsonb_typeof(inference_params)='object')
);
CREATE INDEX IF NOT EXISTS idx_od_model_versions_model ON od_model_versions(model_id);
CREATE INDEX IF NOT EXISTS idx_od_model_versions_stage ON od_model_versions(stage);

-- ========== OD_MODEL_CLASSES ==========
CREATE TABLE IF NOT EXISTS od_model_classes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE CASCADE,
  class_index integer NOT NULL,
  class_name varchar(200) NOT NULL,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT uq_od_model_classes UNIQUE (model_version_id, class_index),
  CONSTRAINT chk_class_name CHECK (char_length(class_name) > 0),
  CONSTRAINT chk_class_index CHECK (class_index >= 0),
  CONSTRAINT chk_class_metadata CHECK (metadata IS NULL OR jsonb_typeof(metadata)='object')
);
CREATE INDEX IF NOT EXISTS idx_od_model_classes_version ON od_model_classes(model_version_id);

-- ========== OD_MODEL_ARTIFACTS ==========
CREATE TABLE IF NOT EXISTS od_model_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE CASCADE,
  artifact_type artifact_type_enum NOT NULL,
  storage_key text NOT NULL,
  file_name varchar(1024) NOT NULL,
  size_bytes bigint,
  sha256 char(64),
  content_type varchar(200),
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_artifact_metadata CHECK (metadata IS NULL OR jsonb_typeof(metadata)='object'),
  CONSTRAINT chk_artifact_size_nonneg CHECK (size_bytes IS NULL OR size_bytes >= 0)
);
CREATE INDEX IF NOT EXISTS idx_od_artifacts_version ON od_model_artifacts(model_version_id);
CREATE INDEX IF NOT EXISTS idx_od_artifacts_type ON od_model_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_od_artifacts_sha ON od_model_artifacts(sha256);
CREATE UNIQUE INDEX IF NOT EXISTS uq_od_artifacts_version_type
  ON od_model_artifacts (model_version_id, artifact_type) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_od_artifacts_version_sha
  ON od_model_artifacts (model_version_id, sha256) WHERE deleted_at IS NULL AND sha256 IS NOT NULL;

-- ========== OD_MODEL_DEPLOYMENTS ==========
CREATE TABLE IF NOT EXISTS od_model_deployments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE CASCADE,
  endpoint_url text,
  runtime jsonb,
  region varchar(64),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_runtime CHECK (runtime IS NULL OR jsonb_typeof(runtime)='object')
);
CREATE INDEX IF NOT EXISTS idx_od_deployments_version ON od_model_deployments(model_version_id);
CREATE INDEX IF NOT EXISTS idx_od_deployments_active ON od_model_deployments(is_active) WHERE deleted_at IS NULL;

-- =========================
-- 2D DATASET & ATTACK TABLES
-- =========================

-- ========== 2D DATASETS ==========
CREATE TABLE IF NOT EXISTS datasets_2d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  owner_id uuid REFERENCES users(id) ON DELETE SET NULL,
  storage_path text NOT NULL,
  metadata jsonb NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_datasets_2d_name CHECK (char_length(name) > 0)
);
CREATE INDEX IF NOT EXISTS idx_datasets_2d_owner ON datasets_2d(owner_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_datasets_2d_owner_name_active
  ON datasets_2d (owner_id, name) WHERE deleted_at IS NULL;

-- ========== 2D IMAGES ==========
CREATE TABLE IF NOT EXISTS images_2d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid NOT NULL REFERENCES datasets_2d(id) ON DELETE CASCADE,
  file_name varchar(1024) NOT NULL,
  storage_key text NOT NULL,
  width integer NULL,
  height integer NULL,
  mime_type varchar(100) NULL,
  metadata jsonb NULL,
  uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_images_dimensions CHECK (
    (width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)
  ),
  CONSTRAINT chk_images_file_name CHECK (char_length(file_name) > 0)
);
CREATE INDEX IF NOT EXISTS idx_images_2d_dataset ON images_2d(dataset_id);
CREATE INDEX IF NOT EXISTS idx_images_2d_file_name ON images_2d(file_name);
CREATE INDEX IF NOT EXISTS idx_images_2d_metadata_gin ON images_2d USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_images_2d_active ON images_2d(dataset_id, created_at)
  WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_images_2d_dataset_file_active
  ON images_2d (dataset_id, file_name) WHERE deleted_at IS NULL;

-- ========== INFERENCE METADATA (YOLO Detection Results) ==========
-- Stores pre-computed inference results for fast class distribution queries
CREATE TABLE IF NOT EXISTS inference_metadata (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid NOT NULL REFERENCES datasets_2d(id) ON DELETE CASCADE,
  model_name varchar(100) NOT NULL,
  inference_timestamp timestamptz NOT NULL,
  total_images integer NOT NULL DEFAULT 0,
  total_detections integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_inference_metadata_dataset UNIQUE (dataset_id)
);
CREATE INDEX IF NOT EXISTS idx_inference_metadata_dataset ON inference_metadata(dataset_id);

-- ========== IMAGE DETECTIONS ==========
-- Individual detection results with bounding boxes
CREATE TABLE IF NOT EXISTS image_detections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  image_id uuid NOT NULL REFERENCES images_2d(id) ON DELETE CASCADE,
  inference_metadata_id uuid NOT NULL REFERENCES inference_metadata(id) ON DELETE CASCADE,
  class_name varchar(50) NOT NULL,
  class_id integer NOT NULL,
  confidence real NOT NULL,
  bbox_x1 real NOT NULL,
  bbox_y1 real NOT NULL,
  bbox_x2 real NOT NULL,
  bbox_y2 real NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_detection_confidence CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT chk_detection_class_id CHECK (class_id >= 0)
);
CREATE INDEX IF NOT EXISTS idx_image_detections_image ON image_detections(image_id);
CREATE INDEX IF NOT EXISTS idx_image_detections_class ON image_detections(class_name);
CREATE INDEX IF NOT EXISTS idx_image_detections_confidence ON image_detections(confidence);
CREATE INDEX IF NOT EXISTS idx_image_detections_inference ON image_detections(inference_metadata_id);

-- ========== DATASET CLASS STATISTICS ==========
-- Pre-computed aggregated statistics per class for instant queries
CREATE TABLE IF NOT EXISTS dataset_class_statistics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid NOT NULL REFERENCES datasets_2d(id) ON DELETE CASCADE,
  class_name varchar(50) NOT NULL,
  class_id integer NOT NULL,
  detection_count integer NOT NULL DEFAULT 0,
  image_count integer NOT NULL DEFAULT 0,
  avg_confidence real NOT NULL,
  min_confidence real NOT NULL,
  max_confidence real NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_dataset_class UNIQUE (dataset_id, class_name),
  CONSTRAINT chk_stats_detection_count CHECK (detection_count >= 0),
  CONSTRAINT chk_stats_image_count CHECK (image_count >= 0),
  CONSTRAINT chk_stats_confidence_range CHECK (
    avg_confidence >= 0 AND avg_confidence <= 1 AND
    min_confidence >= 0 AND min_confidence <= 1 AND
    max_confidence >= 0 AND max_confidence <= 1 AND
    min_confidence <= avg_confidence AND avg_confidence <= max_confidence
  )
);
CREATE INDEX IF NOT EXISTS idx_class_stats_dataset ON dataset_class_statistics(dataset_id);
CREATE INDEX IF NOT EXISTS idx_class_stats_count ON dataset_class_statistics(dataset_id, detection_count DESC);
CREATE INDEX IF NOT EXISTS idx_class_stats_class ON dataset_class_statistics(class_name);

-- ========== 2D PATCHES ==========
CREATE TABLE IF NOT EXISTS patches_2d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  target_model_version_id uuid REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  source_dataset_id uuid REFERENCES datasets_2d(id) ON DELETE SET NULL,
  target_class varchar(200) NULL,
  method varchar(200) NULL,
  hyperparameters jsonb NULL,
  patch_metadata jsonb NULL,
  -- NEW: Storage information (from improvements)
  storage_key text,
  file_name varchar(1024),
  size_bytes bigint,
  sha256 char(64),
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_patches_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_patches_hyperparameters CHECK (
    jsonb_typeof(hyperparameters) = 'object' OR hyperparameters IS NULL
  ),
  CONSTRAINT chk_patches_2d_size_nonneg CHECK (size_bytes IS NULL OR size_bytes >= 0)
);
CREATE INDEX IF NOT EXISTS idx_patches_model_version ON patches_2d(target_model_version_id);
CREATE INDEX IF NOT EXISTS idx_patches_name ON patches_2d(name);
CREATE INDEX IF NOT EXISTS idx_patches_2d_sha ON patches_2d(sha256) WHERE sha256 IS NOT NULL;

-- ========== 2D ATTACK DATASETS ==========
CREATE TABLE IF NOT EXISTS attack_datasets_2d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  attack_type attack_type_enum NOT NULL,
  target_model_version_id uuid REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  base_dataset_id uuid REFERENCES datasets_2d(id) ON DELETE RESTRICT,
  target_class varchar(200) NULL,
  patch_id uuid REFERENCES patches_2d(id) ON DELETE RESTRICT,
  parameters jsonb NULL,
  -- NEW: Experiment linkage (from improvements)
  experiment_id uuid,  -- Will add FK after experiments table is created
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_attack_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_attack_parameters_json CHECK (
    parameters IS NULL OR jsonb_typeof(parameters) = 'object'
  ),
  CONSTRAINT chk_attack_patch_id_required CHECK (
    (attack_type = 'patch' AND patch_id IS NOT NULL) OR
    (attack_type <> 'patch' AND patch_id IS NULL)
  ),
  CONSTRAINT chk_attack_patch_scale_range CHECK (
    attack_type <> 'patch'
    OR parameters->>'patch_scale_ratio' IS NULL
    OR (
         parameters->>'patch_scale_ratio' ~ '^[0-9]*\.?[0-9]+$'
         AND (parameters->>'patch_scale_ratio')::numeric BETWEEN 0.0 AND 1.0
       )
  )
);
CREATE INDEX IF NOT EXISTS idx_attack_type ON attack_datasets_2d(attack_type);
CREATE INDEX IF NOT EXISTS idx_attack_model_version ON attack_datasets_2d(target_model_version_id);
CREATE INDEX IF NOT EXISTS idx_attack_base_dataset ON attack_datasets_2d(base_dataset_id);
CREATE INDEX IF NOT EXISTS idx_attack_patch ON attack_datasets_2d(patch_id);
CREATE INDEX IF NOT EXISTS idx_attack_parameters_gin ON attack_datasets_2d USING GIN (parameters);

-- =========================
-- 3D DATASET & ATTACK TABLES
-- =========================

-- ========== 3D DATASETS ==========
CREATE TABLE IF NOT EXISTS datasets_3d (
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
  -- NEW: JSONB validation (from improvements)
  CONSTRAINT chk_carla_environment_json CHECK (carla_environment IS NULL OR jsonb_typeof(carla_environment) = 'object'),
  CONSTRAINT chk_object_models_json CHECK (object_models IS NULL OR jsonb_typeof(object_models) = 'array'),
  CONSTRAINT chk_metadata_json CHECK (metadata IS NULL OR jsonb_typeof(metadata) = 'object')
);
CREATE INDEX IF NOT EXISTS idx_datasets_3d_owner ON datasets_3d(owner_id);
CREATE INDEX IF NOT EXISTS idx_datasets_3d_env_gin ON datasets_3d USING GIN (carla_environment);
CREATE INDEX IF NOT EXISTS idx_datasets_3d_objects_gin ON datasets_3d USING GIN (object_models);
CREATE UNIQUE INDEX IF NOT EXISTS uq_datasets_3d_owner_name_active
  ON datasets_3d (owner_id, name) WHERE deleted_at IS NULL;

-- ========== 3D IMAGES (CARLA-generated images) ==========
CREATE TABLE IF NOT EXISTS images_3d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid NOT NULL REFERENCES datasets_3d(id) ON DELETE CASCADE,
  file_name varchar(1024) NOT NULL,
  storage_key text NOT NULL,
  width integer NULL,
  height integer NULL,
  mime_type varchar(100) NULL,
  -- 3D-specific metadata: camera info, scene info, etc.
  camera_position jsonb NULL,
  camera_rotation jsonb NULL,
  scene_metadata jsonb NULL,
  metadata jsonb NULL,
  uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_images_3d_dimensions CHECK (
    (width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)
  ),
  CONSTRAINT chk_images_3d_file_name CHECK (char_length(file_name) > 0),
  CONSTRAINT chk_images_3d_camera_pos CHECK (camera_position IS NULL OR jsonb_typeof(camera_position) = 'object'),
  CONSTRAINT chk_images_3d_camera_rot CHECK (camera_rotation IS NULL OR jsonb_typeof(camera_rotation) = 'object'),
  CONSTRAINT chk_images_3d_scene CHECK (scene_metadata IS NULL OR jsonb_typeof(scene_metadata) = 'object')
);
CREATE INDEX IF NOT EXISTS idx_images_3d_dataset ON images_3d(dataset_id);
CREATE INDEX IF NOT EXISTS idx_images_3d_file_name ON images_3d(file_name);
CREATE INDEX IF NOT EXISTS idx_images_3d_metadata_gin ON images_3d USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_images_3d_scene_gin ON images_3d USING GIN (scene_metadata);
CREATE INDEX IF NOT EXISTS idx_images_3d_active ON images_3d(dataset_id, created_at)
  WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_images_3d_dataset_file_active
  ON images_3d (dataset_id, file_name) WHERE deleted_at IS NULL;

-- ========== 3D PATCHES (Texture/image-based patches) ==========
CREATE TABLE IF NOT EXISTS patches_3d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  source_dataset_id uuid REFERENCES datasets_3d(id) ON DELETE SET NULL,
  target_model_version_id uuid REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  target_class varchar(200) NULL,
  method patch3d_method_enum NOT NULL DEFAULT 'texture',
  hyperparameters jsonb NULL,
  patch_metadata jsonb NULL,
  -- NEW: Storage information (from improvements)
  storage_key text,
  file_name varchar(1024),
  size_bytes bigint,
  sha256 char(64),
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_patches_3d_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_patches_3d_hyperparameters CHECK (
    jsonb_typeof(hyperparameters) = 'object' OR hyperparameters IS NULL
  ),
  CONSTRAINT chk_patch_metadata_json CHECK (patch_metadata IS NULL OR jsonb_typeof(patch_metadata) = 'object'),
  CONSTRAINT chk_patches_3d_size_nonneg CHECK (size_bytes IS NULL OR size_bytes >= 0)
);
CREATE INDEX IF NOT EXISTS idx_patches_3d_method ON patches_3d(method);
CREATE INDEX IF NOT EXISTS idx_patches_3d_model_version ON patches_3d(target_model_version_id);
CREATE INDEX IF NOT EXISTS idx_patches_3d_sha ON patches_3d(sha256) WHERE sha256 IS NOT NULL;

-- ========== 3D ATTACK DATASETS ==========
CREATE TABLE IF NOT EXISTS attack_datasets_3d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  base_dataset_id uuid NOT NULL REFERENCES datasets_3d(id) ON DELETE RESTRICT,
  attack_patch_id uuid NOT NULL REFERENCES patches_3d(id) ON DELETE RESTRICT,
  target_model_version_id uuid REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  parameters jsonb NULL,
  placement jsonb GENERATED ALWAYS AS (parameters->'placement') STORED,
  -- NEW: Experiment linkage (from improvements)
  experiment_id uuid,  -- Will add FK after experiments table is created
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_attack_3d_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_attack_3d_params CHECK (parameters IS NULL OR jsonb_typeof(parameters)='object'),
  CONSTRAINT chk_attack_3d_scale_range CHECK (
    parameters->>'patch_scale_ratio' IS NULL
    OR (
         parameters->>'patch_scale_ratio' ~ '^[0-9]*\.?[0-9]+$'
         AND (parameters->>'patch_scale_ratio')::numeric BETWEEN 0.0 AND 1.0
       )
  ),
  CONSTRAINT chk_attack_3d_placement_required CHECK (
    parameters ? 'placement' AND jsonb_typeof(parameters->'placement') = 'object'
  )
);
CREATE INDEX IF NOT EXISTS idx_attack_3d_base_dataset ON attack_datasets_3d(base_dataset_id);
CREATE INDEX IF NOT EXISTS idx_attack_3d_patch ON attack_datasets_3d(attack_patch_id);
CREATE INDEX IF NOT EXISTS idx_attack_3d_model_version ON attack_datasets_3d(target_model_version_id);
CREATE INDEX IF NOT EXISTS idx_attack_3d_params_gin ON attack_datasets_3d USING GIN (parameters);
CREATE INDEX IF NOT EXISTS idx_attack_3d_placement_gin ON attack_datasets_3d USING GIN (placement);

-- =========================
-- REAL-TIME PERFORMANCE MEASUREMENT TABLES
-- =========================

-- ========== CAMERAS ==========
CREATE TABLE IF NOT EXISTS cameras (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  stream_uri text,
  location jsonb,
  resolution jsonb,
  metadata jsonb,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_camera_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_camera_resolution CHECK (resolution IS NULL OR jsonb_typeof(resolution)='object')
);
CREATE INDEX IF NOT EXISTS idx_cameras_active ON cameras(is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cameras_location_gin ON cameras USING GIN (location);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cameras_stream_uri
  ON cameras ((lower(stream_uri))) WHERE deleted_at IS NULL AND stream_uri IS NOT NULL;

-- ========== REAL-TIME CAPTURE RUNS ==========
CREATE TABLE IF NOT EXISTS rt_capture_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  camera_id uuid NOT NULL REFERENCES cameras(id) ON DELETE RESTRICT,
  model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  window_seconds integer NOT NULL DEFAULT 5,
  frames_expected integer NOT NULL DEFAULT 10,
  fps_target numeric(6,3) NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at timestamptz NULL,
  status rt_run_status_enum NOT NULL DEFAULT 'running',
  notes text,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_rt_window CHECK (window_seconds > 0),
  CONSTRAINT chk_rt_frames_expected CHECK (frames_expected > 0),
  CONSTRAINT chk_rt_run_time_range CHECK (ended_at IS NULL OR ended_at >= started_at),
  CONSTRAINT chk_rt_fps_positive CHECK (fps_target IS NULL OR fps_target > 0)
);
CREATE INDEX IF NOT EXISTS idx_rt_runs_camera ON rt_capture_runs(camera_id);
CREATE INDEX IF NOT EXISTS idx_rt_runs_model_version ON rt_capture_runs(model_version_id);
CREATE INDEX IF NOT EXISTS idx_rt_runs_status ON rt_capture_runs(status);
CREATE INDEX IF NOT EXISTS idx_rt_runs_started ON rt_capture_runs(started_at);

-- ========== REAL-TIME FRAMES ==========
CREATE TABLE IF NOT EXISTS rt_frames (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES rt_capture_runs(id) ON DELETE CASCADE,
  seq_no integer NOT NULL,
  captured_at timestamptz NOT NULL DEFAULT now(),
  storage_key text,
  width integer, height integer, mime_type varchar(100),
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT uq_rt_frames_seq UNIQUE (run_id, seq_no),
  CONSTRAINT chk_rt_frames_seq CHECK (seq_no > 0),
  CONSTRAINT chk_rt_frames_wh CHECK (
    (width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)
  )
);
CREATE INDEX IF NOT EXISTS idx_rt_frames_run ON rt_frames(run_id);
CREATE INDEX IF NOT EXISTS idx_rt_frames_captured ON rt_frames(captured_at);

-- ========== REAL-TIME INFERENCES ==========
CREATE TABLE IF NOT EXISTS rt_inferences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  frame_id uuid NOT NULL REFERENCES rt_frames(id) ON DELETE CASCADE,
  model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  latency_ms integer,
  inference jsonb NOT NULL,
  stats jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT uq_rt_inf_frame_model_version UNIQUE (frame_id, model_version_id),
  CONSTRAINT chk_rt_inf_json CHECK (jsonb_typeof(inference)='object'),
  CONSTRAINT chk_rt_inf_latency_nonneg CHECK (latency_ms IS NULL OR latency_ms >= 0)
);
CREATE INDEX IF NOT EXISTS idx_rt_inf_frame ON rt_inferences(frame_id);
CREATE INDEX IF NOT EXISTS idx_rt_inf_model_version ON rt_inferences(model_version_id);
CREATE INDEX IF NOT EXISTS idx_rt_inf_inference_gin ON rt_inferences USING GIN (inference);

-- =========================
-- ANNOTATIONS TABLE (NEW: from improvements)
-- =========================

CREATE TABLE IF NOT EXISTS annotations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  image_2d_id uuid REFERENCES images_2d(id) ON DELETE CASCADE,
  image_3d_id uuid REFERENCES images_3d(id) ON DELETE CASCADE,
  annotation_type annotation_type_enum NOT NULL DEFAULT 'bbox',
  class_name varchar(200) NOT NULL,
  class_index integer,
  -- Bounding box (for bbox type)
  bbox_x numeric(10,2),
  bbox_y numeric(10,2),
  bbox_width numeric(10,2),
  bbox_height numeric(10,2),
  -- Polygon/segmentation data (for polygon/segmentation types)
  polygon_data jsonb,
  -- Keypoints (for keypoint type)
  keypoints jsonb,
  -- Additional metadata
  confidence numeric(5,4) DEFAULT 1.0,
  is_crowd boolean DEFAULT false,
  area numeric(12,2),
  metadata jsonb,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  -- Validation
  CONSTRAINT chk_annotation_class_name CHECK (char_length(class_name) > 0),
  CONSTRAINT chk_annotation_class_index CHECK (class_index IS NULL OR class_index >= 0),
  CONSTRAINT chk_annotation_confidence CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT chk_annotation_bbox CHECK (
    annotation_type <> 'bbox' OR
    (bbox_x IS NOT NULL AND bbox_y IS NOT NULL AND bbox_width > 0 AND bbox_height > 0)
  ),
  CONSTRAINT chk_annotation_polygon CHECK (
    annotation_type <> 'polygon' OR
    (polygon_data IS NOT NULL AND jsonb_typeof(polygon_data) = 'array')
  ),
  CONSTRAINT chk_annotation_keypoints CHECK (
    annotation_type <> 'keypoint' OR
    (keypoints IS NOT NULL AND jsonb_typeof(keypoints) = 'array')
  ),
  CONSTRAINT chk_annotation_area_nonneg CHECK (area IS NULL OR area >= 0),
  -- Either 2D or 3D image, not both
  CONSTRAINT chk_annotation_image_xor CHECK (
    (image_2d_id IS NOT NULL AND image_3d_id IS NULL) OR
    (image_2d_id IS NULL AND image_3d_id IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_annotations_image_2d ON annotations(image_2d_id);
CREATE INDEX IF NOT EXISTS idx_annotations_image_3d ON annotations(image_3d_id);
CREATE INDEX IF NOT EXISTS idx_annotations_class ON annotations(class_name);
CREATE INDEX IF NOT EXISTS idx_annotations_class_idx ON annotations(class_index);
CREATE INDEX IF NOT EXISTS idx_annotations_type ON annotations(annotation_type);
CREATE INDEX IF NOT EXISTS idx_annotations_active_2d ON annotations(image_2d_id, class_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_annotations_active_3d ON annotations(image_3d_id, class_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_annotations_polygon_gin ON annotations USING GIN (polygon_data);
CREATE INDEX IF NOT EXISTS idx_annotations_keypoints_gin ON annotations USING GIN (keypoints);

-- Auto-calculate area for bbox annotations
CREATE OR REPLACE FUNCTION trg_calculate_annotation_area()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.annotation_type = 'bbox' AND NEW.bbox_width IS NOT NULL AND NEW.bbox_height IS NOT NULL THEN
    NEW.area := NEW.bbox_width * NEW.bbox_height;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER annotations_calculate_area_trg
BEFORE INSERT OR UPDATE ON annotations
FOR EACH ROW EXECUTE FUNCTION trg_calculate_annotation_area();

-- =========================
-- EXPERIMENTS TABLE (NEW: from improvements)
-- =========================

CREATE TABLE IF NOT EXISTS experiments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  objective text,
  hypothesis text,
  status experiment_status_enum NOT NULL DEFAULT 'draft',
  started_at timestamptz,
  ended_at timestamptz,
  tags jsonb,
  config jsonb,
  results_summary jsonb,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_experiment_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_experiment_status_time CHECK (
    (status = 'draft' AND started_at IS NULL AND ended_at IS NULL) OR
    (status = 'running' AND started_at IS NOT NULL AND ended_at IS NULL) OR
    (status IN ('completed', 'failed', 'archived') AND started_at IS NOT NULL AND ended_at IS NOT NULL AND ended_at >= started_at)
  ),
  CONSTRAINT chk_experiment_tags CHECK (tags IS NULL OR jsonb_typeof(tags) = 'array'),
  CONSTRAINT chk_experiment_config CHECK (config IS NULL OR jsonb_typeof(config) = 'object'),
  CONSTRAINT chk_experiment_results CHECK (results_summary IS NULL OR jsonb_typeof(results_summary) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_experiments_name_active
  ON experiments(lower(name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_tags_gin ON experiments USING GIN (tags);

-- Add FK constraints for experiment linkage
ALTER TABLE attack_datasets_2d
  ADD CONSTRAINT fk_attack_2d_experiment FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE SET NULL;

ALTER TABLE attack_datasets_3d
  ADD CONSTRAINT fk_attack_3d_experiment FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_attack_2d_experiment ON attack_datasets_2d(experiment_id);
CREATE INDEX IF NOT EXISTS idx_attack_3d_experiment ON attack_datasets_3d(experiment_id);

-- =========================
-- MODEL BENCHMARKS TABLE (NEW: from improvements)
-- =========================

CREATE TABLE IF NOT EXISTS model_benchmarks (
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
  CONSTRAINT chk_benchmark_type CHECK (char_length(benchmark_type) > 0),
  CONSTRAINT chk_benchmark_metrics CHECK (jsonb_typeof(metrics) = 'object'),
  CONSTRAINT chk_benchmark_config CHECK (test_config IS NULL OR jsonb_typeof(test_config) = 'object'),
  CONSTRAINT chk_benchmark_dataset CHECK (
    (dataset_2d_id IS NOT NULL AND dataset_3d_id IS NULL) OR
    (dataset_2d_id IS NULL AND dataset_3d_id IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_benchmarks_model ON model_benchmarks(model_version_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_dataset_2d ON model_benchmarks(dataset_2d_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_dataset_3d ON model_benchmarks(dataset_3d_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_type ON model_benchmarks(benchmark_type);
CREATE INDEX IF NOT EXISTS idx_benchmarks_evaluated ON model_benchmarks(evaluated_at);
CREATE INDEX IF NOT EXISTS idx_benchmarks_metrics_gin ON model_benchmarks USING GIN (metrics);

CREATE UNIQUE INDEX IF NOT EXISTS uq_benchmarks_model_dataset_2d_type
  ON model_benchmarks(model_version_id, dataset_2d_id, benchmark_type)
  WHERE deleted_at IS NULL AND dataset_2d_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_benchmarks_model_dataset_3d_type
  ON model_benchmarks(model_version_id, dataset_3d_id, benchmark_type)
  WHERE deleted_at IS NULL AND dataset_3d_id IS NOT NULL;

-- =========================
-- EVALUATION TABLES
-- =========================

-- ========== EVALUATION RUNS ==========
CREATE TABLE IF NOT EXISTS eval_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  phase eval_phase_enum NOT NULL,
  model_version_id uuid NOT NULL REFERENCES od_model_versions(id) ON DELETE RESTRICT,
  -- NEW: 2D/3D support (from improvements)
  dataset_dimension dataset_dimension_enum NOT NULL DEFAULT '2d',
  base_dataset_id uuid REFERENCES datasets_2d(id) ON DELETE RESTRICT,
  attack_dataset_id uuid REFERENCES attack_datasets_2d(id) ON DELETE RESTRICT,
  base_dataset_3d_id uuid REFERENCES datasets_3d(id) ON DELETE RESTRICT,
  attack_dataset_3d_id uuid REFERENCES attack_datasets_3d(id) ON DELETE RESTRICT,
  -- NEW: Experiment linkage (from improvements)
  experiment_id uuid REFERENCES experiments(id) ON DELETE SET NULL,
  params jsonb,
  metrics_summary jsonb,
  started_at timestamptz,
  ended_at timestamptz,
  status eval_status_enum NOT NULL DEFAULT 'queued',
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_eval_name CHECK (char_length(name) > 0),
  CONSTRAINT chk_eval_params CHECK (params IS NULL OR jsonb_typeof(params)='object'),
  CONSTRAINT chk_eval_metrics_summary CHECK (metrics_summary IS NULL OR jsonb_typeof(metrics_summary)='object'),
  -- NEW: Phase-specific FK requirements (updated for 2D/3D support)
  CONSTRAINT chk_eval_phase_requirements CHECK (
    -- 2D pre-attack
    (dataset_dimension = '2d' AND phase = 'pre_attack' AND base_dataset_id IS NOT NULL
     AND attack_dataset_id IS NULL AND base_dataset_3d_id IS NULL AND attack_dataset_3d_id IS NULL)
    OR
    -- 2D post-attack
    (dataset_dimension = '2d' AND phase = 'post_attack' AND attack_dataset_id IS NOT NULL
     AND base_dataset_3d_id IS NULL AND attack_dataset_3d_id IS NULL)
    OR
    -- 3D pre-attack
    (dataset_dimension = '3d' AND phase = 'pre_attack' AND base_dataset_3d_id IS NOT NULL
     AND attack_dataset_3d_id IS NULL AND base_dataset_id IS NULL AND attack_dataset_id IS NULL)
    OR
    -- 3D post-attack
    (dataset_dimension = '3d' AND phase = 'post_attack' AND attack_dataset_3d_id IS NOT NULL
     AND base_dataset_id IS NULL AND attack_dataset_id IS NULL)
  ),
  CONSTRAINT chk_eval_time_range CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_phase ON eval_runs(phase);
CREATE INDEX IF NOT EXISTS idx_eval_runs_model ON eval_runs(model_version_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_base ON eval_runs(base_dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_attack ON eval_runs(attack_dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON eval_runs(status);
CREATE INDEX IF NOT EXISTS idx_eval_runs_created ON eval_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_eval_runs_phase_status_created ON eval_runs(phase, status, created_at);
-- NEW: 3D indexes (from improvements)
CREATE INDEX IF NOT EXISTS idx_eval_runs_dimension ON eval_runs(dataset_dimension);
CREATE INDEX IF NOT EXISTS idx_eval_runs_base_3d ON eval_runs(base_dataset_3d_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_attack_3d ON eval_runs(attack_dataset_3d_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_experiment ON eval_runs(experiment_id);

-- ========== EVALUATION ITEMS ==========
CREATE TABLE IF NOT EXISTS eval_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  image_2d_id uuid REFERENCES images_2d(id) ON DELETE SET NULL,
  image_3d_id uuid REFERENCES images_3d(id) ON DELETE SET NULL,
  file_name varchar(1024),
  storage_key text,
  ground_truth jsonb,
  prediction jsonb,
  metrics jsonb,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_eval_items_json_gt CHECK (ground_truth IS NULL OR jsonb_typeof(ground_truth)='object' OR jsonb_typeof(ground_truth)='array'),
  CONSTRAINT chk_eval_items_json_pred CHECK (prediction  IS NULL OR jsonb_typeof(prediction)='object'  OR jsonb_typeof(prediction)='array'),
  CONSTRAINT chk_eval_items_json_metrics CHECK (metrics IS NULL OR jsonb_typeof(metrics)='object')
);

CREATE INDEX IF NOT EXISTS idx_eval_items_run ON eval_items(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_items_image_2d ON eval_items(image_2d_id);
CREATE INDEX IF NOT EXISTS idx_eval_items_image_3d ON eval_items(image_3d_id);
CREATE INDEX IF NOT EXISTS idx_eval_items_file ON eval_items(file_name);
CREATE INDEX IF NOT EXISTS idx_eval_items_metrics_gin ON eval_items USING GIN (metrics);
CREATE INDEX IF NOT EXISTS idx_eval_items_active ON eval_items(run_id, created_at) WHERE deleted_at IS NULL;
-- NEW: JSONB indexes (from improvements)
CREATE INDEX IF NOT EXISTS idx_eval_items_gt_gin ON eval_items USING GIN (ground_truth);
CREATE INDEX IF NOT EXISTS idx_eval_items_pred_gin ON eval_items USING GIN (prediction);

-- ========== EVALUATION CLASS METRICS ==========
CREATE TABLE IF NOT EXISTS eval_class_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  class_name varchar(200) NOT NULL,
  metrics jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_eval_class_metrics_json CHECK (jsonb_typeof(metrics)='object')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_class_metrics_run_class
  ON eval_class_metrics(run_id, class_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_eval_class_metrics_run ON eval_class_metrics(run_id);

-- ========== EVALUATION LISTS ==========
CREATE TABLE IF NOT EXISTS eval_lists (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(200) NOT NULL,
  description text,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT chk_eval_lists_name CHECK (char_length(name) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_lists_name_active
  ON eval_lists(lower(name)) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS eval_list_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  list_id uuid NOT NULL REFERENCES eval_lists(id) ON DELETE CASCADE,
  run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL,
  CONSTRAINT uq_eval_list_item UNIQUE (list_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_eval_list_items_list ON eval_list_items(list_id, sort_order);

-- =========================
-- AUDIT LOGS
-- =========================

CREATE TABLE IF NOT EXISTS audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id uuid REFERENCES users(id) NULL,
  action varchar(200) NOT NULL,
  target_type varchar(100) NULL,
  target_id uuid NULL,
  details jsonb NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_audit_action CHECK (char_length(action) > 0),
  CONSTRAINT chk_audit_target_type CHECK (target_type IS NULL OR char_length(target_type) > 0)
);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor_time ON audit_logs(actor_id, created_at) WHERE actor_id IS NOT NULL;
-- NEW: GIN index (from improvements)
CREATE INDEX IF NOT EXISTS idx_audit_details_gin ON audit_logs USING GIN (details);

-- =========================
-- VALIDATION TRIGGERS
-- =========================

-- Update trigger to handle 3D attacks (from improvements)
CREATE OR REPLACE FUNCTION trg_validate_eval_run_attack_base()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  attack_base uuid;
BEGIN
  -- 2D post-attack validation
  IF NEW.dataset_dimension = '2d' AND NEW.phase = 'post_attack' AND NEW.attack_dataset_id IS NOT NULL THEN
    SELECT base_dataset_id INTO attack_base
    FROM attack_datasets_2d
    WHERE id = NEW.attack_dataset_id AND deleted_at IS NULL;

    IF attack_base IS NULL THEN
      RAISE EXCEPTION 'Invalid attack_dataset_id(%) or soft-deleted', NEW.attack_dataset_id
        USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF NEW.base_dataset_id IS NULL THEN
      NEW.base_dataset_id := attack_base;
    ELSIF NEW.base_dataset_id <> attack_base THEN
      RAISE EXCEPTION 'base_dataset_id(%) must match attack base_dataset_id(%) for 2D post_attack runs',
        NEW.base_dataset_id, attack_base USING ERRCODE = 'check_violation';
    END IF;
  END IF;

  -- 3D post-attack validation
  IF NEW.dataset_dimension = '3d' AND NEW.phase = 'post_attack' AND NEW.attack_dataset_3d_id IS NOT NULL THEN
    SELECT base_dataset_id INTO attack_base
    FROM attack_datasets_3d
    WHERE id = NEW.attack_dataset_3d_id AND deleted_at IS NULL;

    IF attack_base IS NULL THEN
      RAISE EXCEPTION 'Invalid attack_dataset_3d_id(%) or soft-deleted', NEW.attack_dataset_3d_id
        USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF NEW.base_dataset_3d_id IS NULL THEN
      NEW.base_dataset_3d_id := attack_base;
    ELSIF NEW.base_dataset_3d_id <> attack_base THEN
      RAISE EXCEPTION 'base_dataset_3d_id(%) must match attack base_dataset_id(%) for 3D post_attack runs',
        NEW.base_dataset_3d_id, attack_base USING ERRCODE = 'check_violation';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'eval_runs_validate_attack_base_trg') THEN
    CREATE TRIGGER eval_runs_validate_attack_base_trg
    BEFORE INSERT OR UPDATE ON eval_runs
    FOR EACH ROW EXECUTE FUNCTION trg_validate_eval_run_attack_base();
  END IF;
END $$;

-- =========================
-- UPDATED_AT TRIGGERS
-- =========================

DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname AS tbl
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname = 'public'
      AND c.relname IN (
        'users',
        'datasets_2d','images_2d','patches_2d','attack_datasets_2d',
        'datasets_3d','images_3d','patches_3d','attack_datasets_3d',
        'cameras','rt_capture_runs','rt_frames','rt_inferences',
        'od_models','od_model_versions','od_model_classes','od_model_artifacts','od_model_deployments',
        'eval_runs','eval_items','eval_class_metrics','eval_lists',
        'annotations', 'experiments', 'model_benchmarks',
        'dataset_class_statistics'
      )
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = r.tbl || '_set_updated_at_trg') THEN
      EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at()',
        r.tbl || '_set_updated_at_trg',
        r.tbl
      );
    END IF;
  END LOOP;
END $$;

-- Validate completion for rt_capture_runs
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'rt_capture_runs_validate_on_complete_trg') THEN
    CREATE TRIGGER rt_capture_runs_validate_on_complete_trg
    BEFORE UPDATE ON rt_capture_runs
    FOR EACH ROW EXECUTE FUNCTION trg_validate_run_completion();
  END IF;
END $$;

-- =========================
-- HELPER VIEWS
-- =========================

-- Compare pre vs post evaluation runs for same model/base_dataset/attack_dataset
CREATE OR REPLACE VIEW eval_run_pairs AS
SELECT
  pre.id  AS pre_run_id,
  post.id AS post_run_id,
  pre.model_version_id,
  pre.base_dataset_id,
  post.attack_dataset_id,
  pre.metrics_summary AS pre_metrics,
  post.metrics_summary AS post_metrics,
  pre.created_at AS pre_created_at,
  post.created_at AS post_created_at
FROM eval_runs pre
JOIN eval_runs post
  ON post.phase = 'post_attack'
 AND pre.phase = 'pre_attack'
 AND pre.model_version_id = post.model_version_id
 AND pre.base_dataset_id = post.base_dataset_id
WHERE pre.deleted_at IS NULL AND post.deleted_at IS NULL;

-- Delta calculation view
CREATE OR REPLACE VIEW eval_run_pairs_delta AS
SELECT
  pre_run_id,
  post_run_id,
  model_version_id,
  base_dataset_id,
  attack_dataset_id,
  (pre_metrics->>'mAP')::numeric AS pre_map,
  (post_metrics->>'mAP')::numeric AS post_map,
  ((post_metrics->>'mAP')::numeric - (pre_metrics->>'mAP')::numeric) AS delta_map
FROM eval_run_pairs;

-- NEW: Materialized View for experiment summary (from improvements)
-- Note: For production use, consider refreshing via cron job instead of triggers
-- to avoid performance overhead on high-frequency INSERT/UPDATE operations.
-- Example cron: REFRESH MATERIALIZED VIEW CONCURRENTLY experiment_summary;
CREATE MATERIALIZED VIEW IF NOT EXISTS experiment_summary AS
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
GROUP BY e.id, e.name, e.status, e.started_at, e.ended_at, e.created_at, e.created_by;

-- Create unique index for CONCURRENTLY refresh support
CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_summary_id ON experiment_summary(id);

-- Optional: Uncomment below for auto-refresh (may impact performance on bulk operations)
-- If using triggers, ensure initial data exists before enabling CONCURRENTLY option
/*
CREATE OR REPLACE FUNCTION refresh_experiment_summary()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- Use CONCURRENTLY only if unique index exists and has data
  REFRESH MATERIALIZED VIEW CONCURRENTLY experiment_summary;
  RETURN NULL;
EXCEPTION
  WHEN OTHERS THEN
    -- Fallback to non-concurrent refresh if concurrent fails
    REFRESH MATERIALIZED VIEW experiment_summary;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_refresh_exp_summary_on_experiment
AFTER INSERT OR UPDATE OR DELETE ON experiments
FOR EACH STATEMENT EXECUTE FUNCTION refresh_experiment_summary();

CREATE TRIGGER trg_refresh_exp_summary_on_attack_2d
AFTER INSERT OR UPDATE OR DELETE ON attack_datasets_2d
FOR EACH STATEMENT EXECUTE FUNCTION refresh_experiment_summary();

CREATE TRIGGER trg_refresh_exp_summary_on_attack_3d
AFTER INSERT OR UPDATE OR DELETE ON attack_datasets_3d
FOR EACH STATEMENT EXECUTE FUNCTION refresh_experiment_summary();

CREATE TRIGGER trg_refresh_exp_summary_on_eval_runs
AFTER INSERT OR UPDATE OR DELETE ON eval_runs
FOR EACH STATEMENT EXECUTE FUNCTION refresh_experiment_summary();
*/

-- NEW: Model benchmarks comparison view (from improvements)
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
ORDER BY m.name, mv.version, mb.evaluated_at DESC;

-- NEW: Image annotations summary view (from improvements)
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
GROUP BY i.id, i.file_name, i.dataset_id;

-- NEW: Dataset class distribution view (from inference metadata)
CREATE OR REPLACE VIEW dataset_class_distribution AS
SELECT
  d.id AS dataset_id,
  d.name AS dataset_name,
  im.model_name,
  im.inference_timestamp,
  im.total_images,
  im.total_detections,
  cs.class_name,
  cs.class_id,
  cs.detection_count,
  cs.image_count,
  cs.avg_confidence,
  cs.min_confidence,
  cs.max_confidence,
  ROUND((cs.detection_count::numeric / NULLIF(im.total_detections, 0) * 100), 2) AS percentage
FROM datasets_2d d
JOIN inference_metadata im ON d.id = im.dataset_id
JOIN dataset_class_statistics cs ON d.id = cs.dataset_id
WHERE d.deleted_at IS NULL
ORDER BY d.name, cs.detection_count DESC;

-- =========================
-- COMMENTS FOR DOCUMENTATION
-- =========================

COMMENT ON TABLE annotations IS 'Ground truth annotations for images (bounding boxes, polygons, keypoints)';
COMMENT ON TABLE experiments IS 'Research experiments grouping multiple attacks and evaluations';
COMMENT ON TABLE model_benchmarks IS 'Baseline performance metrics for model versions on clean datasets';
COMMENT ON TABLE inference_metadata IS 'Pre-computed YOLO inference results for datasets (performance: 750x faster than real-time inference)';
COMMENT ON TABLE image_detections IS 'Individual detection records with bounding boxes from pre-computed inference';
COMMENT ON TABLE dataset_class_statistics IS 'Aggregated class statistics for instant top-classes queries (<10ms response time)';
COMMENT ON COLUMN eval_runs.dataset_dimension IS 'Dataset dimension: 2d or 3d';
COMMENT ON COLUMN eval_runs.base_dataset_3d_id IS '3D base dataset for 3D evaluations';
COMMENT ON COLUMN eval_runs.attack_dataset_3d_id IS '3D attack dataset for 3D post-attack evaluations';
COMMENT ON COLUMN patches_2d.storage_key IS 'Storage path for generated patch image';
COMMENT ON COLUMN patches_3d.storage_key IS 'Storage path for generated 3D patch texture/model';
COMMENT ON COLUMN annotations.annotation_type IS 'Type of annotation: bbox, polygon, keypoint, segmentation';
COMMENT ON COLUMN experiments.tags IS 'Searchable tags for experiment categorization';
COMMENT ON COLUMN model_benchmarks.benchmark_type IS 'Type of benchmark: clean, augmented, adversarial_robust, etc.';
COMMENT ON COLUMN inference_metadata.model_name IS 'Model used for inference (e.g., YOLO11n, YOLOv8x)';
COMMENT ON COLUMN dataset_class_statistics.detection_count IS 'Total number of detections for this class across all images';
COMMENT ON COLUMN dataset_class_statistics.image_count IS 'Number of images containing at least one detection of this class';

-- =====================================================================
-- Integration Notes & Schema Design Principles:
--
-- 1. UNIFIED MODEL REFERENCE:
--    - od_model_versions is the SINGLE SOURCE OF TRUTH for all model references
--    - All attack datasets, patches, and real-time captures reference od_model_versions
--
-- 2. DOMAIN TABLES:
--    - 2D Attack: datasets_2d, images_2d, patches_2d, attack_datasets_2d
--    - 2D Inference Metadata: inference_metadata, image_detections, dataset_class_statistics
--    - 3D Attack (patch-only): datasets_3d, images_3d, patches_3d, attack_datasets_3d
--    - Real-time: cameras, rt_capture_runs, rt_frames, rt_inferences
--    - Model Repository: od_models, od_model_versions, od_model_classes,
--      od_model_artifacts, od_model_deployments
--    - Evaluation: eval_runs, eval_items, eval_class_metrics, eval_lists
--    - NEW: Annotations, Experiments, Model Benchmarks
--
-- 3. NEW FEATURES (from schema_improvements.sql):
--    - 3D Evaluation Support: eval_runs now supports both 2D and 3D datasets
--    - Patches Storage Info: patches_2d/3d now track storage_key, file_name, size, sha256
--    - Annotations Table: Ground truth storage with bbox, polygon, keypoint, segmentation
--    - Experiments Table: Research experiment management with status workflow
--    - Model Benchmarks: Baseline performance metrics for model versions
--    - Enhanced JSONB Validation: Stronger type checking on 3D datasets
--    - Inference Metadata: Pre-computed YOLO results for 750x performance boost (7.5s → 10ms)
--
-- 4. DATA INTEGRITY:
--    - Soft Delete: All tables have deleted_at
--    - FK Delete Rules: RESTRICT for critical data, SET NULL for audit, CASCADE for dependent
--    - Enhanced Constraints: experiment status-time consistency, annotation area auto-calc
--
-- 5. PERFORMANCE OPTIMIZATIONS:
--    - GIN indexes for JSONB fields
--    - Partial indexes for active records (WHERE deleted_at IS NULL)
--    - Materialized view for experiment summary (manual refresh recommended)
--    - Composite indexes for common query patterns
--
-- 6. EVALUATION WORKFLOW:
--    - Pre-attack: Baseline on clean dataset (2D or 3D)
--    - Post-attack: Adversarial on attacked dataset (2D or 3D)
--    - Automatic validation of dataset matching
--    - Experiment grouping for research organization
-- =====================================================================

COMMIT;
