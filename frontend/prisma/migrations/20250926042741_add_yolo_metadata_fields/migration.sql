-- AlterTable
ALTER TABLE "public"."Dataset" ADD COLUMN     "inferenceData" JSONB,
ADD COLUMN     "modelName" TEXT,
ADD COLUMN     "targetClass" TEXT;

-- AlterTable
ALTER TABLE "public"."ImageFile" ADD COLUMN     "detections" JSONB,
ADD COLUMN     "visualization" TEXT;
