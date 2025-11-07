-- CreateTable
CREATE TABLE "public"."EvaluationRecord" (
    "id" TEXT NOT NULL,
    "modelName" TEXT NOT NULL,
    "modelVersion" TEXT NOT NULL,
    "evaluationType" TEXT NOT NULL,
    "accuracy" DOUBLE PRECISION,
    "precision" DOUBLE PRECISION,
    "recall" DOUBLE PRECISION,
    "f1Score" DOUBLE PRECISION,
    "processingTime" DOUBLE PRECISION,
    "datasetSize" INTEGER,
    "successRate" DOUBLE PRECISION,
    "notes" TEXT,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "EvaluationRecord_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."AdversarialTest" (
    "id" TEXT NOT NULL,
    "evaluationId" TEXT NOT NULL,
    "attackType" TEXT NOT NULL,
    "epsilon" DOUBLE PRECISION,
    "successRate" DOUBLE PRECISION NOT NULL,
    "robustness" DOUBLE PRECISION NOT NULL,
    "originalAccuracy" DOUBLE PRECISION,
    "attackedAccuracy" DOUBLE PRECISION,
    "sampleCount" INTEGER NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AdversarialTest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."PerformanceTest" (
    "id" TEXT NOT NULL,
    "evaluationId" TEXT NOT NULL,
    "testType" TEXT NOT NULL,
    "metric" TEXT NOT NULL,
    "value" DOUBLE PRECISION NOT NULL,
    "unit" TEXT NOT NULL,
    "conditions" TEXT,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "PerformanceTest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."Dataset" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "source" TEXT,
    "size" INTEGER NOT NULL,
    "storageLocation" TEXT,
    "description" TEXT,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Dataset_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."DataGeneration" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "generationType" TEXT NOT NULL,
    "parameters" JSONB NOT NULL,
    "outputCount" INTEGER NOT NULL,
    "status" TEXT NOT NULL,
    "startTime" TIMESTAMP(3),
    "endTime" TIMESTAMP(3),
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DataGeneration_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."SystemLog" (
    "id" TEXT NOT NULL,
    "level" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "details" JSONB,
    "userId" TEXT,
    "sessionId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SystemLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SystemLog_level_category_idx" ON "public"."SystemLog"("level", "category");

-- CreateIndex
CREATE INDEX "SystemLog_createdAt_idx" ON "public"."SystemLog"("createdAt");

-- AddForeignKey
ALTER TABLE "public"."AdversarialTest" ADD CONSTRAINT "AdversarialTest_evaluationId_fkey" FOREIGN KEY ("evaluationId") REFERENCES "public"."EvaluationRecord"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."PerformanceTest" ADD CONSTRAINT "PerformanceTest_evaluationId_fkey" FOREIGN KEY ("evaluationId") REFERENCES "public"."EvaluationRecord"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."DataGeneration" ADD CONSTRAINT "DataGeneration_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "public"."Dataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;
