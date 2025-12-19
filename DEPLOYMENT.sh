#!/bin/bash
# Deployment and runtime guide for async event ingestion system

# 1. BUILD DOCKER IMAGE
docker build -t pulseboard:latest .

# 2. START SERVICES
docker-compose up -d

# 3. RUN MIGRATIONS
docker-compose exec api alembic upgrade head

# 4. VERIFY SERVICES
docker-compose ps

# 5. VIEW LOGS
docker-compose logs -f api          # API server
docker-compose logs -f worker       # Celery worker
docker-compose logs -f celery-beat  # Celery beat scheduler
docker-compose logs -f flower       # Flower monitoring

# 6. MONITOR TASKS
# Access Flower at: http://localhost:5555

# 7. STOP SERVICES
docker-compose down

# 8. CLEAN UP
docker-compose down -v  # Remove volumes
