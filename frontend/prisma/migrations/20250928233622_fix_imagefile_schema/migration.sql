/*
  Warnings:

  - You are about to drop the column `originalName` on the `ImageFile` table. All the data in the column will be lost.
  - You are about to drop the column `path` on the `ImageFile` table. All the data in the column will be lost.
  - You are about to drop the column `url` on the `ImageFile` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "public"."ImageFile" DROP COLUMN "originalName",
DROP COLUMN "path",
DROP COLUMN "url";

-- CreateTable
CREATE TABLE "public"."adversarial_training" (
    "id" SERIAL NOT NULL,
    "target_class" VARCHAR(50) NOT NULL,
    "target_class_id" INTEGER NOT NULL,
    "model_path" VARCHAR(255) NOT NULL,
    "patch_size" INTEGER NOT NULL,
    "area_ratio" DOUBLE PRECISION NOT NULL,
    "epsilon" DOUBLE PRECISION NOT NULL,
    "alpha" DOUBLE PRECISION NOT NULL,
    "iterations" INTEGER NOT NULL,
    "batch_size" INTEGER NOT NULL,
    "best_score" DOUBLE PRECISION,
    "patch_file_path" VARCHAR(500),
    "patch_data" TEXT,
    "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "patch_name" VARCHAR(255),
    "dataset_id" VARCHAR(255),
    "dataset_name" VARCHAR(255),
    "inference_json_path" VARCHAR(500),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP(3),

    CONSTRAINT "adversarial_training_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "adversarial_training_status_idx" ON "public"."adversarial_training"("status");

-- CreateIndex
CREATE INDEX "idx_adversarial_training_patch_name" ON "public"."adversarial_training"("patch_name");

-- CreateIndex
CREATE INDEX "idx_adversarial_training_dataset_id" ON "public"."adversarial_training"("dataset_id");
