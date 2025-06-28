# Create New Worktree

## Overview
Create a new git worktree with isolated Docker configuration, database, and ports for parallel development of the Discord bot.

## Prerequisites
- Worktree environment initialized (`@worktrees/init-worktree.md`)
- Main branch is clean and up-to-date
- Available Discord bot token (if testing multiple instances)

## Quick Create

### 1. Create Worktree for New Feature
```bash
# Syntax: git worktree add <path> <branch-name>
git worktree add ../zgdk-feature-name feature/new-feature

# Or create from existing branch
git worktree add ../zgdk-feature-name existing-branch
```

### 2. Setup Worktree Configuration
```bash
# Navigate to new worktree
cd ../zgdk-feature-name

# Allocate ports and generate config
WORKTREE_NAME=$(basename $(pwd))
python3 .worktrees/scripts/manage-ports.py allocate $WORKTREE_NAME > .worktree-config.env

# Source the configuration
source .worktree-config.env

# Generate .env file
sed -e "s/{{WORKTREE_NAME}}/$WORKTREE_NAME/g" \
    -e "s/{{APP_PORT}}/$APP_PORT/g" \
    -e "s/{{DB_PORT}}/$DB_PORT/g" \
    .worktrees/configs/env.template > .env

# Generate docker-compose.yml
sed -e "s/{{WORKTREE_NAME}}/$WORKTREE_NAME/g" \
    -e "s/{{APP_PORT}}/$APP_PORT/g" \
    -e "s/{{DB_PORT}}/$DB_PORT/g" \
    -e "s/{{PREFIX}}/$PREFIX/g" \
    -e "s/{{DB_NAME}}/zgdk_$WORKTREE_NAME/g" \
    .worktrees/configs/docker-compose.template.yml > docker-compose.yml
```

## Automated Create Script

### Create Helper Script
```bash
# Create automated worktree creation script
cat > .worktrees/scripts/create-worktree.sh << 'EOF'
#!/bin/bash

set -e

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <worktree-name> <branch-name> [base-branch]"
    echo "Example: $0 feature-auth feature/auth-system main"
    exit 1
fi

WORKTREE_NAME="$1"
BRANCH_NAME="$2"
BASE_BRANCH="${3:-main}"

# Validate worktree name (no special chars except dash/underscore)
if [[ ! "$WORKTREE_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Worktree name can only contain letters, numbers, dashes, and underscores"
    exit 1
fi

# Check if we're in the main repo
if [ ! -d ".worktrees" ]; then
    echo "Error: Must be run from main repository directory"
    exit 1
fi

WORKTREE_PATH="../zgdk-$WORKTREE_NAME"

echo "Creating worktree: $WORKTREE_NAME"
echo "Branch: $BRANCH_NAME"
echo "Path: $WORKTREE_PATH"

# Create the worktree
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "Using existing branch: $BRANCH_NAME"
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "Creating new branch: $BRANCH_NAME from $BASE_BRANCH"
    git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "$BASE_BRANCH"
fi

# Navigate to worktree
cd "$WORKTREE_PATH"

echo "Setting up worktree configuration..."

# Allocate ports and get configuration
CONFIG=$(python3 .worktrees/scripts/manage-ports.py allocate "$WORKTREE_NAME")
APP_PORT=$(echo "$CONFIG" | grep APP_PORT | cut -d= -f2)
DB_PORT=$(echo "$CONFIG" | grep DB_PORT | cut -d= -f2)
PREFIX=$(echo "$CONFIG" | grep PREFIX | cut -d= -f2)

echo "Allocated ports - App: $APP_PORT, DB: $DB_PORT"

# Generate .env file
sed -e "s/{{WORKTREE_NAME}}/$WORKTREE_NAME/g" \
    -e "s/{{APP_PORT}}/$APP_PORT/g" \
    -e "s/{{DB_PORT}}/$DB_PORT/g" \
    .worktrees/configs/env.template > .env

# Generate docker-compose.yml
sed -e "s/{{WORKTREE_NAME}}/$WORKTREE_NAME/g" \
    -e "s/{{APP_PORT}}/$APP_PORT/g" \
    -e "s/{{DB_PORT}}/$DB_PORT/g" \
    -e "s/{{PREFIX}}/$PREFIX/g" \
    -e "s/{{DB_NAME}}/zgdk_$WORKTREE_NAME/g" \
    .worktrees/configs/docker-compose.template.yml > docker-compose.yml

# Create worktree-specific gitignore additions
cat >> .gitignore << 'WORKTREE_EOF'

# Worktree-specific files
.worktree-config.env
docker-compose.override.yml
WORKTREE_EOF

echo ""
echo "✅ Worktree created successfully!"
echo ""
echo "Next steps:"
echo "1. cd $WORKTREE_PATH"
echo "2. Edit .env file (add Discord token, etc.)"
echo "3. Run: docker-compose up --build"
echo "4. Start developing!"
echo ""
echo "Ports allocated:"
echo "  - App: http://localhost:$APP_PORT"
echo "  - Database: localhost:$DB_PORT"
echo ""
echo "To remove this worktree later:"
echo "  bash .worktrees/scripts/remove-worktree.sh $WORKTREE_NAME"

EOF

chmod +x .worktrees/scripts/create-worktree.sh
```

## Usage Examples

### Create Feature Branch Worktree
```bash
# Create new feature branch and worktree
bash .worktrees/scripts/create-worktree.sh feature-auth feature/auth-system

# Create worktree from existing branch
bash .worktrees/scripts/create-worktree.sh fix-bugs bugfix/database-constraints
```

### Manual Steps After Creation
```bash
# Navigate to your new worktree
cd ../zgdk-feature-auth

# Edit .env file with your Discord token
nano .env
# Add: DISCORD_TOKEN=your_token_here

# Start the isolated environment
docker-compose up --build

# In another terminal, check if it's working
docker-compose logs app --tail=20
```

## Configuration Details

### Generated .env File Contains
- Unique database name: `zgdk_<worktree-name>`
- Isolated ports for app and database
- Worktree-specific environment variables
- Same bot configuration as main

### Generated docker-compose.yml Contains
- Unique container names: `zgdk-app-<worktree-name>`
- Isolated networks: `zgdk-network-<worktree-name>`
- Separated volumes: `zgdk_postgres_data_<worktree-name>`
- Non-conflicting ports

## Troubleshooting

### Port Already in Use
```bash
# Check what's using the port
lsof -i :8001

# Or kill all containers and restart
docker-compose down
docker-compose up --build
```

### Database Connection Issues
```bash
# Check database container
docker-compose ps
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up --build
```

### Worktree Creation Fails
```bash
# Check if branch exists
git branch -a

# Check worktree list
git worktree list

# Remove failed worktree
git worktree remove ../zgdk-feature-name --force
```

## Important Notes

⚠️ **Discord Token**: Use different bot tokens for simultaneous testing
⚠️ **Database**: Each worktree has its own isolated database
⚠️ **Ports**: Automatically allocated to avoid conflicts
⚠️ **Memory**: Multiple Docker instances use more RAM