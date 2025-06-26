# Initialize Worktree Environment

## Overview
Set up the foundational configuration for using git worktrees with the Discord bot project. This handles port management, database isolation, and container naming conflicts.

## Prerequisites
- Git repository initialized
- Docker and docker-compose installed
- Main branch working and tested

## Initial Setup

### 1. Create Worktree Configuration Directory
```bash
mkdir -p .worktrees/configs
mkdir -p .worktrees/scripts
```

### 2. Create Port Allocation Registry
```bash
# Create port registry file
cat > .worktrees/port-registry.json << 'EOF'
{
  "main": {
    "app_port": 8000,
    "db_port": 5432,
    "prefix": "zgdk"
  },
  "allocated_ports": {
    "8000": "main",
    "5432": "main"
  },
  "next_available": {
    "app_port": 8001,
    "db_port": 5433
  }
}
EOF
```

### 3. Create Base Environment Template
```bash
# Create template .env file for worktrees
cat > .worktrees/configs/env.template << 'EOF'
# Discord Bot Configuration
DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE
DISCORD_GUILD_ID=YOUR_GUILD_ID

# Database Configuration  
POSTGRES_USER=zgdk_user
POSTGRES_PASSWORD=zgdk_password
POSTGRES_DB=zgdk_{{WORKTREE_NAME}}
POSTGRES_HOST=localhost
POSTGRES_PORT={{DB_PORT}}

# Bot Configuration
BOT_PREFIX=!
DEBUG=True

# Worktree Specific
WORKTREE_NAME={{WORKTREE_NAME}}
WORKTREE_PORT={{APP_PORT}}
EOF
```

### 4. Create Docker Compose Template
```bash
# Create template docker-compose for worktrees
cat > .worktrees/configs/docker-compose.template.yml << 'EOF'
version: '3.8'

services:
  app:
    build: .
    container_name: {{PREFIX}}-app-{{WORKTREE_NAME}}
    ports:
      - "{{APP_PORT}}:8000"
    environment:
      - POSTGRES_HOST=db
      - POSTGRES_PORT=5432
      - POSTGRES_DB={{DB_NAME}}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - DISCORD_GUILD_ID=${DISCORD_GUILD_ID}
    depends_on:
      - db
    volumes:
      - .:/app
    networks:
      - {{PREFIX}}-network-{{WORKTREE_NAME}}

  db:
    image: postgres:15
    container_name: {{PREFIX}}-db-{{WORKTREE_NAME}}
    ports:
      - "{{DB_PORT}}:5432"
    environment:
      - POSTGRES_DB={{DB_NAME}}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - {{PREFIX}}_postgres_data_{{WORKTREE_NAME}}:/var/lib/postgresql/data
    networks:
      - {{PREFIX}}-network-{{WORKTREE_NAME}}

volumes:
  {{PREFIX}}_postgres_data_{{WORKTREE_NAME}}:

networks:
  {{PREFIX}}-network-{{WORKTREE_NAME}}:
    driver: bridge
EOF
```

### 5. Create Worktree Management Script
```bash
cat > .worktrees/scripts/manage-ports.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import os

def load_registry():
    with open('.worktrees/port-registry.json', 'r') as f:
        return json.load(f)

def save_registry(data):
    with open('.worktrees/port-registry.json', 'w') as f:
        json.dump(data, f, indent=2)

def allocate_ports(worktree_name):
    registry = load_registry()
    
    app_port = registry['next_available']['app_port']
    db_port = registry['next_available']['db_port']
    
    # Check if already allocated
    if worktree_name in registry:
        return registry[worktree_name]
    
    # Allocate new ports
    registry[worktree_name] = {
        'app_port': app_port,
        'db_port': db_port,
        'prefix': 'zgdk'
    }
    
    registry['allocated_ports'][str(app_port)] = worktree_name
    registry['allocated_ports'][str(db_port)] = worktree_name
    
    # Update next available
    registry['next_available']['app_port'] = app_port + 1
    registry['next_available']['db_port'] = db_port + 1
    
    save_registry(registry)
    return registry[worktree_name]

def deallocate_ports(worktree_name):
    registry = load_registry()
    
    if worktree_name in registry:
        config = registry[worktree_name]
        del registry['allocated_ports'][str(config['app_port'])]
        del registry['allocated_ports'][str(config['db_port'])]
        del registry[worktree_name]
        save_registry(registry)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: manage-ports.py [allocate|deallocate] <worktree_name>")
        sys.exit(1)
    
    action = sys.argv[1]
    worktree_name = sys.argv[2]
    
    if action == 'allocate':
        config = allocate_ports(worktree_name)
        print(f"APP_PORT={config['app_port']}")
        print(f"DB_PORT={config['db_port']}")
        print(f"PREFIX={config['prefix']}")
    elif action == 'deallocate':
        deallocate_ports(worktree_name)
        print(f"Deallocated ports for {worktree_name}")
EOF

chmod +x .worktrees/scripts/manage-ports.py
```

### 6. Update .gitignore
```bash
# Add worktree-specific ignores
cat >> .gitignore << 'EOF'

# Worktree configurations
.worktrees/configs/*.env
.worktrees/configs/docker-compose.*.yml
.worktrees/port-registry.json
EOF
```

## Verification

### Test Port Allocation
```bash
cd .worktrees/scripts
python3 manage-ports.py allocate test-feature
# Should output: APP_PORT=8001, DB_PORT=5433, PREFIX=zgdk
```

### Verify File Structure
```bash
tree .worktrees/
# Should show:
# .worktrees/
# ├── configs/
# │   ├── env.template
# │   └── docker-compose.template.yml
# └── scripts/
#     └── manage-ports.py
```

## Next Steps
After initialization, you can:
1. Create new worktrees with `@worktrees/create-worktree.md`
2. Manage existing worktrees with other guides
3. Each worktree will have isolated ports and databases

## Important Notes
- **Discord Token**: You'll need separate bot tokens for simultaneous testing
- **Database**: Each worktree gets its own PostgreSQL database
- **Ports**: Automatically allocated to avoid conflicts
- **Containers**: Uniquely named per worktree