-- CreateTable
CREATE TABLE "public"."adversarial_training_logs" (
    "id" SERIAL NOT NULL,
    "training_id" INTEGER NOT NULL,
    "iteration" INTEGER NOT NULL,
    "avg_loss" DOUBLE PRECISION,
    "detected_count" INTEGER,
    "total_count" INTEGER,
    "message" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "adversarial_training_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."adversarial_results" (
    "id" SERIAL NOT NULL,
    "training_id" INTEGER NOT NULL,
    "original_image_path" VARCHAR(500) NOT NULL,
    "adversarial_image_path" VARCHAR(500) NOT NULL,
    "visualized_image_path" VARCHAR(500),
    "original_detections" INTEGER NOT NULL,
    "adversarial_detections" INTEGER NOT NULL,
    "reduction" INTEGER NOT NULL,
    "bboxes" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "adversarial_results_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_adversarial_training_logs_training_id" ON "public"."adversarial_training_logs"("training_id");

-- CreateIndex
CREATE INDEX "idx_adversarial_results_training_id" ON "public"."adversarial_results"("training_id");

-- AddForeignKey
ALTER TABLE "public"."adversarial_training_logs" ADD CONSTRAINT "adversarial_training_logs_training_id_fkey" FOREIGN KEY ("training_id") REFERENCES "public"."adversarial_training"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."adversarial_results" ADD CONSTRAINT "adversarial_results_training_id_fkey" FOREIGN KEY ("training_id") REFERENCES "public"."adversarial_training"("id") ON DELETE CASCADE ON UPDATE CASCADE;
