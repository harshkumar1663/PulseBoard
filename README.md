# PulseBoard Backend

Production-grade real-time operational analytics backend built with FastAPI.

## Features

- **JWT Authentication**: Access and refresh token flow
- **Event Ingestion API**: High-throughput event collection with batch support
- **Real-time Metrics**: WebSocket streaming of live metric updates
- **Background Processing**: Celery workers for async event processing and aggregation
- **Redis Caching**: Fast metric access and pub/sub for real-time updates
- **PostgreSQL**: Robust data storage with SQLAlchemy 2.0 async
- **Alembic Migrations**: Database schema version control
- **Docker Compose**: Full stack orchestration

## Tech Stack

- FastAPI (async)
- PostgreSQL + SQLAlchemy 2.0
- Redis
- Celery + Celery Beat
- WebSockets
- JWT Authentication
- Alembic
- Docker

## Quick Start

1. **Copy environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Update `.env` with secure values** (especially `SECRET_KEY`)

3. **Start all services**:
   ```bash
   docker compose up -d
   ```

4. **Run database migrations**:
   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Access the application**:
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/api/v1/docs
   - Flower (Celery monitoring): http://localhost:5555

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get tokens
- `POST /api/v1/auth/refresh` - Refresh access token

### Users
- `GET /api/v1/users/me` - Get current user
- `PUT /api/v1/users/me` - Update current user
- `DELETE /api/v1/users/me` - Delete account

### Events
- `POST /api/v1/events` - Ingest single event
- `POST /api/v1/events/batch` - Batch ingest events
- `GET /api/v1/events` - Query user events
- `GET /api/v1/events/{id}` - Get specific event

### Metrics
- `POST /api/v1/metrics` - Create metric data point
- `GET /api/v1/metrics` - Query metrics
- `GET /api/v1/metrics/{id}` - Get specific metric
- `GET /api/v1/metrics/aggregate/{name}` - Get aggregated metrics
- `GET /api/v1/metrics/latest/{name}` - Get latest cached metric

### WebSocket
- `WS /api/v1/ws/metrics?token={jwt}` - Real-time metric updates

## Architecture

```
app/
├── api/          # FastAPI route handlers
├── core/         # Configuration, security, dependencies
├── db/           # Database session, Redis client
├── models/       # SQLAlchemy ORM models
├── schemas/      # Pydantic request/response schemas
├── services/     # Business logic layer
└── workers/      # Celery tasks and configuration
```

## Development

### Create database migration:
```bash
docker compose exec backend alembic revision --autogenerate -m "description"
```

### Apply migrations:
```bash
docker compose exec backend alembic upgrade head
```

### View logs:
```bash
docker compose logs -f backend
docker compose logs -f celery-worker
```

### Run tests:
```bash
docker compose exec backend pytest
```

## Production Deployment

1. Set strong `SECRET_KEY` in production
2. Set `DEBUG=False`
3. Configure proper CORS origins
4. Use production-grade PostgreSQL instance
5. Scale Celery workers based on load
6. Set up monitoring (Prometheus, Grafana)
7. Configure SSL/TLS termination
8. Set up proper logging aggregation

## Monitoring

- **Flower**: Celery task monitoring at http://localhost:5555
- **Health Check**: GET /health
- **Metrics**: Redis caching for real-time dashboards

## License

MIT
