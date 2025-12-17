# Setup script for PulseBoard backend (PowerShell)

Write-Host "Setting up PulseBoard backend..." -ForegroundColor Green

# Copy environment file if not exists
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "Please update .env with secure SECRET_KEY before running!" -ForegroundColor Red
}

# Build and start services
Write-Host "Building Docker images..." -ForegroundColor Green
docker compose build

Write-Host "Starting services..." -ForegroundColor Green
docker compose up -d postgres redis

# Wait for PostgreSQL to be ready
Write-Host "Waiting for PostgreSQL..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "Starting backend services..." -ForegroundColor Green
docker compose up -d

# Wait for backend to be ready
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Run migrations
Write-Host "Running database migrations..." -ForegroundColor Green
docker compose exec -T backend alembic upgrade head

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Services running:" -ForegroundColor Cyan
Write-Host "  - API: http://localhost:8000"
Write-Host "  - API Docs: http://localhost:8000/api/v1/docs"
Write-Host "  - Flower: http://localhost:5555"
Write-Host ""
Write-Host "To view logs: docker compose logs -f" -ForegroundColor Yellow
Write-Host "To stop: docker compose down" -ForegroundColor Yellow
