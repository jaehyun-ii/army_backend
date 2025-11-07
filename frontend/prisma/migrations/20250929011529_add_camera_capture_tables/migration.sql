-- CreateTable
CREATE TABLE "public"."camera_captures" (
    "id" SERIAL NOT NULL,
    "model_path" VARCHAR(255) NOT NULL,
    "total_images" INTEGER NOT NULL DEFAULT 10,
    "duration_seconds" INTEGER NOT NULL DEFAULT 5,
    "status" VARCHAR(50) NOT NULL DEFAULT 'in_progress',
    "avg_confidence_overall" DOUBLE PRECISION,
    "total_detections" INTEGER DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP(3),

    CONSTRAINT "camera_captures_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."camera_capture_images" (
    "id" SERIAL NOT NULL,
    "capture_id" INTEGER NOT NULL,
    "image_path" VARCHAR(500) NOT NULL,
    "frame_number" INTEGER NOT NULL,
    "detections" JSONB,
    "avg_confidence" DOUBLE PRECISION,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "camera_capture_images_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_camera_captures_created_at" ON "public"."camera_captures"("created_at" DESC);

-- CreateIndex
CREATE INDEX "idx_camera_capture_images_capture_id" ON "public"."camera_capture_images"("capture_id");

-- CreateIndex
CREATE INDEX "idx_camera_capture_images_frame_number" ON "public"."camera_capture_images"("frame_number");

-- AddForeignKey
ALTER TABLE "public"."camera_capture_images" ADD CONSTRAINT "camera_capture_images_capture_id_fkey" FOREIGN KEY ("capture_id") REFERENCES "public"."camera_captures"("id") ON DELETE CASCADE ON UPDATE CASCADE;
