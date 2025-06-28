# Docker Deployment Guide

## Quick Start

### Using Docker Hub Image

```bash
# Pull the latest image
docker pull ppyzel/zgdk:latest

# Run with docker-compose
wget https://raw.githubusercontent.com/parimple/zgdk/main/docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Variables

Create a `.env` file with the following variables:

```env
# Discord Bot Token
DISCORD_TOKEN=your_discord_bot_token

# Database Configuration
POSTGRES_USER=zgdk
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=zgdk
POSTGRES_PORT=5432

# API Tokens
TIPO_API_TOKEN=your_tipo_token

# AI Configuration (optional)
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

## Health Checks

The container includes built-in health checks:
- Health endpoint: `http://localhost:8091/health`
- Check interval: 30 seconds
- Timeout: 10 seconds
- Start period: 60 seconds

### Verify Health Status

```bash
# Check container health
docker ps

# Check health endpoint
curl http://localhost:8091/health

# View health check logs
docker inspect <container_name> --format='{{json .State.Health}}'
```

## Monitoring

The bot exposes the following ports:
- `8000` - Main application port
- `8090` - Metrics/monitoring port
- `8091` - Health check port

## Updates

```bash
# Pull latest version
docker pull ppyzel/zgdk:latest

# Restart containers
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Check Logs
```bash
docker-compose logs app --tail=100
```

### Database Connection Issues
```bash
docker-compose exec db psql -U zgdk -d zgdk
```

### Reset Database
```bash
docker-compose down -v
docker-compose up -d
```

## Building from Source

If you want to build the image yourself:

```bash
git clone https://github.com/parimple/zgdk.git
cd zgdk
docker build -f docker/app/Dockerfile -t zgdk-app:custom .
```

## Architecture

- Base image: `python:3.10-slim-buster`
- Process manager: `dumb-init`
- Database: PostgreSQL 15.2
- Health monitoring: Built-in health check script

## Support

For issues and questions:
- GitHub Issues: https://github.com/parimple/zgdk/issues
- Discord: [Your Discord Server]