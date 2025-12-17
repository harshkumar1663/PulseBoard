#!/bin/bash
# Setup script for PulseBoard backend

set -e

echo "Setting up PulseBoard backend..."

# Copy environment file if not exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please update .env with secure SECRET_KEY before running!"
fi

# Build and start services
echo "Building Docker images..."
docker compose build

echo "Starting services..."
docker compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
sleep 5

echo "Starting backend services..."
docker compose up -d

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 5

# Run migrations
echo "Running database migrations..."
docker compose exec -T backend alembic upgrade head

echo ""
echo "✅ Setup complete!"
echo ""
echo "Services running:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/api/v1/docs"
echo "  - Flower: http://localhost:5555"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop: docker compose down"
