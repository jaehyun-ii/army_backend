# Project Libraries & Services

This document provides a comprehensive list of all libraries, dependencies, and services used across the `army_ai` project, including the backend, frontend, and infrastructure services.

## 1. Infrastructure and Services (`docker-compose.yml`)

The project uses Docker to containerize its services. The following services are defined:

-   **`postgres:15-alpine`**: The primary database for the application.
-   **`dpage/pgadmin4:latest`**: A web-based administration tool for the PostgreSQL database.
-   **`backend` (Custom Docker image)**: The FastAPI backend application.
-   **`frontend` (Custom Docker image)**: The Next.js frontend application.

---

## 2. Backend Libraries (`/backend`)

The backend is a Python application built with FastAPI.

### Core Dependencies (`requirements.txt`)

-   **Server & Framework**:
    -   `fastapi==0.109.0`
    -   `uvicorn[standard]==0.27.0`
    -   `python-multipart==0.0.6`
-   **Database**:
    -   `sqlalchemy==2.0.25`
    -   `asyncpg==0.29.0`
    -   `psycopg2-binary==2.9.9`
-   **Validation & Settings**:
    -   `pydantic==2.5.3`
    -   `pydantic-settings==2.1.0`
    -   `email-validator==2.1.0`
-   **Authentication & Security**:
    -   `python-jose[cryptography]==3.3.0`
    -   `PyJWT==2.8.0`
    -   `passlib[bcrypt]==1.7.4`
-   **Utilities**:
    -   `python-dateutil==2.8.2`
    -   `python-dotenv==1.0.0`
    -   `pyyaml==6.0.1`
-   **Image Processing**:
    -   `opencv-python-headless==4.9.0.80`
    -   `numpy==1.26.4`
    -   `Pillow==10.2.0`

### Development Dependencies (`requirements-dev.txt`)

-   **Testing**:
    -   `pytest==7.4.4`
    -   `pytest-asyncio==0.21.1`
    -   `pytest-cov==4.1.0`
    -   `pytest-mock==3.12.0`
    -   `httpx==0.25.2`
    -   `aiosqlite==0.19.0`
    -   `factory-boy==3.3.0`
    -   `faker==20.1.0`
    -   `fakeredis==2.20.1`
-   **Code Quality & Linting**:
    -   `black==23.12.1`
    -   `isort==5.13.2`
    -   `flake8==7.0.0`
    -   `mypy==1.8.0`
    -   `pylint==3.0.3`
    -   `pre-commit==3.6.0`
-   **Documentation**:
    -   `mkdocs==1.5.3`
    -   `mkdocs-material==9.5.3`
    -   `mkdocstrings[python]==0.24.0`
-   **Debugging & Profiling**:
    -   `ipython==8.19.0`
    -   `ipdb==0.13.13`
    -   `py-spy==0.3.14`
    -   `memory-profiler==0.61.0`
-   **Security & Load Testing**:
    -   `bandit==1.7.6`
    -   `safety==3.0.1`
    -   `locust==2.20.0`

---

## 3. Frontend Libraries (`/frontend`)

The frontend is a Next.js application with a desktop version built using Electron.

### Core Dependencies (`package.json`)

-   **Framework & Core**:
    -   `next: ^14.2.32`
    -   `react: ^18`
    -   `react-dom: ^18`
-   **UI Components & Styling (Radix UI, etc.)**:
    -   `@radix-ui/...`: A suite of components for building design systems.
    -   `class-variance-authority: ^0.7.1`
    -   `clsx: ^2.1.1`
    -   `tailwind-merge: ^2.5.5`
    -   `tailwindcss-animate: ^1.0.7`
    -   `lucide-react: ^0.454.0`
    -   `recharts: 2.15.4`
    -   `sonner: ^1.7.4`
    -   `vaul: ^0.9.9`
-   **Forms**:
    -   `@hookform/resolvers: ^3.10.0`
    -   `react-hook-form: ^7.60.0`
    -   `zod: 3.25.67`
-   **Database & Auth**:
    -   `@prisma/client: ^6.16.2`
    -   `bcryptjs: ^3.0.2`
    -   `jsonwebtoken: ^9.0.2`
-   **Server & Utilities**:
    -   `express: ^5.1.0`
    -   `http-proxy-middleware: ^3.0.5`
    -   `date-fns: 4.1.0`
    -   `geist: ^1.3.1`
    -   `next-themes: ^0.4.6`
    -   `@vercel/analytics: 1.3.1`

### Development & Build Dependencies (`package.json`)

-   **TypeScript & Linting**:
    -   `@types/...`: Various type definitions for libraries.
    -   `typescript: ^5`
-   **Styling & Build Tools**:
    -   `autoprefixer: ^10.4.20`
    -   `postcss: ^8.5`
    -   `@tailwindcss/postcss: ^4.1.9`
    -   `tailwindcss: ^4.1.9`
-   **Electron & Desktop App**:
    -   `electron: ^38.1.0`
    -   `electron-builder: ^26.0.12`
    -   `electron-is-dev: ^3.0.1`
-   **Utilities**:
    -   `concurrently: ^9.2.1`
    -   `cross-env: ^10.0.0`
    -   `wait-on: ^8.0.5`
    -   `prisma: ^6.16.2`
    -   `tsx`: For running TypeScript scripts.