# Docker Structure

This directory contains all Docker-related files for the ZGDK bot.

## Structure

```
docker/
├── app/
│   └── Dockerfile          # Main application container
├── mcp/
│   └── Dockerfile          # MCP server container
├── db/
│   └── init.sql           # Database initialization (if needed)
├── docker-compose.full.yml # Complete stack with all services
├── docker-compose.override.yml # Override configurations
└── docker-compose.mcp.yml  # MCP-specific compose file
```

## Usage

### Basic Usage

From the project root directory:

```bash
# Build and run main application
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f app
```

### Advanced Usage

```bash
# Run full stack with MCP server
docker-compose -f docker/docker-compose.full.yml --profile mcp up --build

# Use override configuration
docker-compose -f docker-compose.yml -f docker/docker-compose.override.yml up

# Run only MCP services
docker-compose -f docker/docker-compose.mcp.yml up
```

### Common Commands

```bash
# Rebuild containers
docker-compose down && docker-compose up --build

# Check for errors
docker-compose logs app --tail=100 | grep -E "(ERROR|Failed)"

# Monitor live logs
docker-compose logs app --follow --tail=50

# Clean up volumes
docker-compose down -v
```

## Environment Variables

Required variables in `.env`:
- `ZAGADKA_TOKEN` - Discord bot token
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name
- `TIPO_API_TOKEN` - Tipo API token (optional)
- `ENABLE_MCP` - Enable MCP server (optional)

## Troubleshooting

### Common Issues

1. **Port conflicts**: Check if ports 5432, 8000, 8089, 8090 are available
2. **Database connection**: Ensure PostgreSQL is running and credentials are correct
3. **Discord token**: Verify token is valid and bot has proper permissions
4. **Docker build**: Clear cache with `docker-compose build --no-cache`

### Debugging

```bash
# Access container shell
docker-compose exec app /bin/bash

# Check PostgreSQL logs
docker-compose logs db

# Test database connection
docker-compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB
```