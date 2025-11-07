-- CreateTable
CREATE TABLE "public"."ImageFile" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "originalName" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "url" TEXT,
    "size" INTEGER NOT NULL,
    "width" INTEGER,
    "height" INTEGER,
    "format" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ImageFile_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ImageFile_datasetId_idx" ON "public"."ImageFile"("datasetId");

-- AddForeignKey
ALTER TABLE "public"."ImageFile" ADD CONSTRAINT "ImageFile_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "public"."Dataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;
