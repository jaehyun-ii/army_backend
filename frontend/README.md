# Adversarial Vision Platform - Frontend

CSS 없는 Next.js 기반 프론트엔드 애플리케이션입니다.

## 기능

백엔드 테스트 코드와 FRONTEND_SCENARIOS.md를 기반으로 구현된 5가지 주요 시나리오:

1. **2D 적대적 패치 생성** (`/attacks/adversarial-patch/create`)
   - 데이터셋 및 모델 선택
   - 타겟 클래스 자동 추천 (상위 5개 클래스)
   - 패치 생성 및 다운로드

2. **노이즈 공격 데이터셋 생성** (`/attacks/noise-attack/create`)
   - FGSM, PGD, Gaussian Noise 공격 지원
   - 공격 타입별 파라미터 설정
   - Targeted/Untargeted 공격 선택

3. **모델 평가 및 비교** (`/evaluation/create`, `/evaluation/compare`)
   - Pre-attack/Post-attack 평가
   - 실시간 평가 진행 모니터링 (2초마다 폴링)
   - 평가 결과 비교 및 공격 성공률 계산

4. **실시간 카메라 탐지** (`/realtime/sessions/create`)
   - 카메라 선택 및 세션 설정
   - WebSocket 기반 실시간 스트리밍
   - 탐지 결과 실시간 표시
   - 세션 통계 및 결과 분석

5. **실험 관리** (`/experiments/create`)
   - 실험 생성 (이름, 설명, 가설, 파라미터)
   - 실험 Run 추가 (파라미터, 메트릭, 아티팩트)
   - 실험 결과 추적

## 프로젝트 구조

```
frontend/
├── app/
│   ├── layout.tsx                    # 루트 레이아웃 (네비게이션 포함)
│   ├── page.tsx                      # 홈 페이지
│   ├── attacks/
│   │   ├── adversarial-patch/
│   │   │   ├── create/page.tsx      # 패치 생성
│   │   │   └── result/[patchId]/page.tsx  # 패치 결과
│   │   └── noise-attack/
│   │       └── create/page.tsx       # 노이즈 공격 생성
│   ├── evaluation/
│   │   ├── create/page.tsx           # 평가 실행
│   │   ├── runs/[runId]/page.tsx    # 평가 진행/결과
│   │   └── compare/page.tsx          # 평가 비교
│   ├── realtime/
│   │   ├── cameras/page.tsx          # 카메라 목록
│   │   └── sessions/
│   │       ├── create/page.tsx       # 세션 생성
│   │       └── [sessionId]/
│   │           ├── live/page.tsx     # 실시간 스트림
│   │           └── results/page.tsx  # 세션 결과
│   ├── experiments/
│   │   ├── create/page.tsx           # 실험 생성
│   │   └── [experimentId]/page.tsx   # 실험 상세
│   ├── datasets/page.tsx             # 데이터셋 목록
│   └── models/page.tsx               # 모델 목록
├── lib/
│   └── api.ts                        # API 클라이언트
├── package.json
├── tsconfig.json
└── next.config.js

## 설치 및 실행

### 1. 의존성 설치

```bash
npm install
```

### 2. 개발 서버 실행

```bash
npm run dev
```

서버가 http://localhost:3000 에서 실행됩니다.

### 3. 백엔드 연결

백엔드 API가 http://localhost:8000 에서 실행되어야 합니다.
Next.js가 자동으로 `/api/v1/*` 요청을 백엔드로 프록시합니다.

## API 엔드포인트

### Adversarial Patch
- `POST /api/v1/adversarial-patch/patches/generate` - 패치 생성
- `GET /api/v1/adversarial-patch/patches/{id}` - 패치 조회
- `GET /api/v1/adversarial-patch/patches/{id}/download` - 패치 다운로드

### Noise Attack
- `POST /api/v1/noise-attack/fgsm/generate` - FGSM 공격
- `POST /api/v1/noise-attack/pgd/generate` - PGD 공격
- `POST /api/v1/noise-attack/gaussian/generate` - Gaussian Noise

### Evaluation
- `POST /api/v1/evaluation/runs` - 평가 실행
- `GET /api/v1/evaluation/runs/{id}` - 평가 상태 조회
- `POST /api/v1/evaluation/runs/compare` - 평가 결과 비교

### Realtime
- `GET /api/v1/realtime/cameras` - 카메라 목록
- `POST /api/v1/realtime/runs` - 세션 시작
- `WS /api/v1/realtime/stream/{id}` - 실시간 스트림 (WebSocket)
- `POST /api/v1/realtime/runs/{id}/stop` - 세션 종료

### Datasets & Models
- `GET /api/v1/datasets-2d` - 데이터셋 목록
- `GET /api/v1/datasets-2d/{id}/top-classes` - 상위 클래스 조회
- `GET /api/v1/models` - 모델 목록

### Experiments
- `POST /api/v1/experiments` - 실험 생성
- `GET /api/v1/experiments/{id}` - 실험 조회
- `POST /api/v1/experiments/{id}/results` - Run 추가

## 주요 기능 설명

### 1. 데이터셋 기반 클래스 추천

데이터셋 선택 시 자동으로 상위 5개 클래스를 추천합니다.
- 메타데이터 기반 조회 (10ms, 750배 빠름)
- 클래스별 탐지 수, 비율, 평균 신뢰도 표시

### 2. 실시간 평가 모니터링

평가 진행 중 2초마다 상태를 폴링하여 실시간으로 진행 상황을 표시합니다.

### 3. WebSocket 스트리밍

실시간 카메라 세션에서 WebSocket을 통해 프레임과 탐지 결과를 스트리밍합니다.

### 4. 파라미터 관리

학습 및 공격 파라미터는 백엔드에서 관리되며, 프론트엔드는 필수 항목만 입력합니다:
- ✅ 데이터셋 선택
- ✅ 모델 선택
- ✅ 타겟 클래스 선택
- ❌ 학습 파라미터 (백엔드 기본값 사용)

## 스타일링

이 프로젝트는 **CSS 없이** 순수 HTML 요소만 사용합니다:
- 기본 HTML 태그 (`<table>`, `<form>`, `<input>` 등)
- 인라인 스타일 최소한만 사용 (border, padding 등)
- 브라우저 기본 스타일 활용

## 빌드

```bash
npm run build
npm start
```

## 개발 시 주의사항

1. **타입 안전성**: TypeScript를 사용하지만 `any` 타입을 허용했습니다.
2. **에러 처리**: 모든 API 호출에 try-catch 블록 포함
3. **상태 관리**: React hooks (useState, useEffect) 사용
4. **클라이언트 컴포넌트**: 모든 페이지는 `'use client'` 지시어 사용

## 참고 문서

- 백엔드 API: `/Users/gimjaehyeon/Downloads/army_backend/backend/docs/FRONTEND_SCENARIOS.md`
- 테스트 코드: `/Users/gimjaehyeon/Downloads/army_backend/backend/tests/`
