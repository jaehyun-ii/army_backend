-- Performance Metrics Table
-- Stores detailed COCO-style metrics for datasets

CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    model_id UUID REFERENCES model_repo(id) ON DELETE SET NULL,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Core AP Metrics (Average Precision)
    ap_map FLOAT,           -- mAP@[.5:.95] (main metric)
    ap_50 FLOAT,            -- AP@IoU=0.50
    ap_75 FLOAT,            -- AP@IoU=0.75
    ap_small FLOAT,         -- AP for small objects
    ap_medium FLOAT,        -- AP for medium objects
    ap_large FLOAT,         -- AP for large objects

    -- Core AR Metrics (Average Recall)
    ar_1 FLOAT,             -- AR@1 (max 1 detection per image)
    ar_10 FLOAT,            -- AR@10 (max 10 detections per image)
    ar_100 FLOAT,           -- AR@100 (max 100 detections per image)
    ar_small FLOAT,         -- AR for small objects
    ar_medium FLOAT,        -- AR for medium objects
    ar_large FLOAT,         -- AR for large objects

    -- Per-class metrics (stored as JSONB for flexibility)
    per_class_ap JSONB,     -- {class_name: ap_value, ...}
    per_class_ar JSONB,     -- {class_name: ar_value, ...}

    -- Precision-Recall curves (for later analysis)
    precision_recall_curve JSONB,  -- {iou_threshold: {recall_values: [...], precision_values: [...]}, ...}

    -- Additional metadata
    num_images INTEGER,
    num_detections INTEGER,
    num_ground_truths INTEGER,

    -- Unique constraint to prevent duplicate metrics
    UNIQUE(dataset_id, model_id)
);

CREATE INDEX idx_performance_metrics_dataset ON performance_metrics(dataset_id);
CREATE INDEX idx_performance_metrics_model ON performance_metrics(model_id);
CREATE INDEX idx_performance_metrics_created ON performance_metrics(created_at DESC);


-- Robustness Comparison Table
-- Stores comparison metrics between clean and adversarial datasets

CREATE TABLE IF NOT EXISTS robustness_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clean_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    adversarial_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    model_id UUID REFERENCES model_repo(id) ON DELETE SET NULL,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Clean dataset metrics (reference)
    ap_clean FLOAT,
    ap_50_clean FLOAT,
    ap_75_clean FLOAT,
    ar_100_clean FLOAT,

    -- Adversarial dataset metrics
    ap_adv FLOAT,
    ap_50_adv FLOAT,
    ap_75_adv FLOAT,
    ar_100_adv FLOAT,

    -- Change/Drop metrics
    delta_ap FLOAT,                 -- AP_clean - AP_adv
    drop_percentage FLOAT,          -- (ΔAP / AP_clean) × 100
    robustness_ratio FLOAT,         -- AP_adv / AP_clean

    delta_ap_50 FLOAT,
    drop_percentage_50 FLOAT,
    robustness_ratio_50 FLOAT,

    delta_ap_75 FLOAT,
    drop_percentage_75 FLOAT,
    robustness_ratio_75 FLOAT,

    delta_ar_100 FLOAT,
    drop_percentage_ar FLOAT,
    robustness_ratio_ar FLOAT,

    -- Recall@IoU changes
    delta_recall_50 FLOAT,          -- Recall drop at IoU=0.5
    delta_recall_75 FLOAT,          -- Recall drop at IoU=0.75

    -- Precision@Recall changes
    precision_at_recall_50_clean FLOAT,    -- Precision when recall=0.5 (clean)
    precision_at_recall_50_adv FLOAT,      -- Precision when recall=0.5 (adversarial)
    delta_precision_at_recall_50 FLOAT,    -- Difference

    -- Per-class robustness (stored as JSONB)
    per_class_robustness JSONB,     -- {class_name: {delta_ap, drop_pct, ratio}, ...}

    -- Additional metadata
    attack_type VARCHAR(50),         -- 'patch' or 'noise'
    notes TEXT,

    -- Unique constraint
    UNIQUE(clean_dataset_id, adversarial_dataset_id, model_id)
);

CREATE INDEX idx_robustness_metrics_clean ON robustness_metrics(clean_dataset_id);
CREATE INDEX idx_robustness_metrics_adv ON robustness_metrics(adversarial_dataset_id);
CREATE INDEX idx_robustness_metrics_model ON robustness_metrics(model_id);
CREATE INDEX idx_robustness_metrics_created ON robustness_metrics(created_at DESC);


-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_performance_metrics_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER performance_metrics_updated_at
    BEFORE UPDATE ON performance_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_performance_metrics_updated_at();

CREATE TRIGGER robustness_metrics_updated_at
    BEFORE UPDATE ON robustness_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_performance_metrics_updated_at();
