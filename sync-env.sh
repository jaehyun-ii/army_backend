#!/bin/bash

# ==============================================
# Environment Variables Synchronization Script
# ==============================================
# This script syncs .env files from root to subdirectories
# Usage: ./sync-env.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_ENV="${SCRIPT_DIR}/.env"

echo "======================================"
echo "Environment Variables Sync"
echo "======================================"

# Check if root .env exists
if [ ! -f "$ROOT_ENV" ]; then
    echo "❌ Error: Root .env file not found at $ROOT_ENV"
    echo "Please create .env file from .env.example:"
    echo "  cp .env.example .env"
    exit 1
fi

# Load root .env
echo "📖 Loading root .env file..."
set -a
source "$ROOT_ENV"
set +a

# ==================
# Database .env
# ==================
echo ""
echo "📝 Syncing database/.env..."
cat > "${SCRIPT_DIR}/database/.env" <<EOF
# PostgreSQL Configuration
POSTGRES_USER=${POSTGRES_USER:-admin}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-adminpw}
POSTGRES_DB=${POSTGRES_DB:-armydb}
POSTGRES_PORT=${POSTGRES_PORT:-5432}

# pgAdmin Configuration
PGADMIN_EMAIL=${PGADMIN_EMAIL:-admin@example.com}
PGADMIN_PASSWORD=${PGADMIN_PASSWORD:-adminpw}
PGADMIN_PORT=${PGADMIN_PORT:-5050}

# Database Connection String (for application)
DATABASE_URL=postgresql://${POSTGRES_USER:-admin}:${POSTGRES_PASSWORD:-adminpw}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-armydb}
EOF
echo "✅ database/.env synced"

# ==================
# Backend .env
# ==================
echo ""
echo "📝 Syncing backend/.env..."
cat > "${SCRIPT_DIR}/backend/.env" <<EOF
# Database Configuration
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-admin}:${POSTGRES_PASSWORD:-adminpw}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-armydb}

# Security
SECRET_KEY=${SECRET_KEY:-your-secret-key-change-this-in-production}
ALGORITHM=${ALGORITHM:-HS256}
ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES:-30}

# Application
APP_NAME=${APP_NAME:-Army AI Platform API}
DEBUG=${DEBUG:-False}
API_PREFIX=${API_PREFIX:-/api/v1}
LOG_LEVEL=${LOG_LEVEL:-INFO}

# Storage
STORAGE_ROOT=${STORAGE_ROOT:-./storage}
STORAGE_TYPE=${STORAGE_TYPE:-local}

# S3 Configuration (if STORAGE_TYPE=s3)
# AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
# AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
# AWS_REGION=${AWS_REGION:-us-east-1}
# S3_BUCKET=${S3_BUCKET:-army-ai-storage}

# Cache
CACHE_TYPE=memory
EOF
echo "✅ backend/.env synced"

# ==================
# Frontend .env
# ==================
echo ""
echo "📝 Syncing frontend/.env..."
cat > "${SCRIPT_DIR}/frontend/.env" <<EOF
# Database URL for Prisma
DATABASE_URL=postgresql://${POSTGRES_USER:-admin}:${POSTGRES_PASSWORD:-adminpw}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-armydb}?schema=public

# NextAuth Configuration
NEXTAUTH_URL=${NEXTAUTH_URL:-http://localhost:3000}
NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-your-nextauth-secret-change-this}
JWT_SECRET=${JWT_SECRET:-your-jwt-secret-change-this}

# Node Environment
NODE_ENV=${NODE_ENV:-production}

# API URLs
NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
NEXT_PUBLIC_BACKEND_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
BACKEND_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
NEXT_PUBLIC_FLASK_API_URL=${NEXT_PUBLIC_FLASK_API_URL:-http://localhost:5000}
EOF
echo "✅ frontend/.env synced"

echo ""
echo "======================================"
echo "✅ All .env files synced successfully!"
echo "======================================"
echo ""
echo "Synced files:"
echo "  - database/.env"
echo "  - backend/.env"
echo "  - frontend/.env"
echo ""
echo "Note: For Docker deployment, environment variables are"
echo "managed by docker-compose.yml using the root .env file."
