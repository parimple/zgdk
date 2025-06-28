# Remove Worktree and Cleanup

## Overview
Safely remove git worktrees with complete cleanup of Docker containers, databases, allocated ports, and filesystem resources for the Discord bot project.

## Prerequisites
- Existing worktree to be removed
- All important work committed and pushed (or merged via PR)
- Understanding of what will be permanently deleted

## Pre-Removal Checklist

### 1. Backup Important Work
```bash
# Navigate to worktree you want to remove
cd ../zgdk-your-feature

# Check for uncommitted changes
git status

# Check if branch is pushed to remote
git log --oneline @{u}..  # Shows unpushed commits
# If output is empty, all commits are pushed

# List local files not in git
git clean -n  # Shows what would be removed (dry run)
```

### 2. Verify Safe to Remove
```bash
# Ensure work is preserved elsewhere
echo "Checking worktree safety..."
echo "Branch: $(git branch --show-current)"
echo "Last commit: $(git log -1 --oneline)"
echo "Remote status: $(git remote -v)"

# Check if branch exists on remote
if git ls-remote --exit-code --heads origin $(git branch --show-current); then
    echo "✅ Branch exists on remote"
else
    echo "⚠️ Branch NOT on remote - push first if needed"
fi
```

## Safe Removal Process

### Method 1: Automated Cleanup Script
```bash
# Create comprehensive removal script
cat > .worktrees/scripts/remove-worktree.sh << 'EOF'
#!/bin/bash

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Usage check
if [ $# -lt 1 ]; then
    echo "Usage: $0 <worktree-name> [--force]"
    echo "Example: $0 feature-auth"
    echo "         $0 feature-auth --force  (skip confirmations)"
    exit 1
fi

WORKTREE_NAME="$1"
FORCE_MODE="${2:-}"

# Determine worktree path
WORKTREE_PATH="../zgdk-$WORKTREE_NAME"

# Check if we're in main repo directory
if [ ! -d ".worktrees" ]; then
    echo -e "${RED}Error: Must be run from main repository directory${NC}"
    exit 1
fi

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    echo -e "${RED}Error: Worktree path does not exist: $WORKTREE_PATH${NC}"
    echo "Available worktrees:"
    git worktree list
    exit 1
fi

echo -e "${YELLOW}Removing worktree: $WORKTREE_NAME${NC}"
echo -e "${YELLOW}Path: $WORKTREE_PATH${NC}"

# Safety confirmation unless forced
if [ "$FORCE_MODE" != "--force" ]; then
    echo ""
    echo -e "${RED}⚠️  WARNING: This will permanently delete:${NC}"
    echo "  - Worktree directory: $WORKTREE_PATH"
    echo "  - Docker containers: zgdk-*-$WORKTREE_NAME"
    echo "  - Docker volumes: zgdk_postgres_data_$WORKTREE_NAME"
    echo "  - Database: zgdk_$WORKTREE_NAME"
    echo "  - Allocated ports for this worktree"
    echo ""
    
    # Check for uncommitted changes
    cd "$WORKTREE_PATH"
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo -e "${RED}⚠️  UNCOMMITTED CHANGES DETECTED:${NC}"
        git status --short
        echo ""
    fi
    
    # Check for unpushed commits
    UNPUSHED=$(git log --oneline @{u}.. 2>/dev/null || git log --oneline HEAD~10..HEAD)
    if [ -n "$UNPUSHED" ]; then
        echo -e "${RED}⚠️  UNPUSHED COMMITS DETECTED:${NC}"
        echo "$UNPUSHED"
        echo ""
    fi
    
    cd - > /dev/null
    
    read -p "Continue with removal? (type 'yes' to confirm): " -r
    if [ "$REPLY" != "yes" ]; then
        echo "Removal cancelled"
        exit 1
    fi
fi

echo ""
echo "Starting cleanup process..."

# Step 1: Stop and remove Docker containers
echo -e "${GREEN}[1/6] Stopping Docker containers...${NC}"
cd "$WORKTREE_PATH"

if [ -f "docker-compose.yml" ]; then
    # Stop containers
    docker-compose down || echo "Containers already stopped"
    
    # Remove containers explicitly
    docker rm -f "zgdk-app-$WORKTREE_NAME" 2>/dev/null || echo "App container already removed"
    docker rm -f "zgdk-db-$WORKTREE_NAME" 2>/dev/null || echo "DB container already removed"
    
    # Remove volumes
    docker volume rm "zgdk_postgres_data_$WORKTREE_NAME" 2>/dev/null || echo "Volume already removed"
    
    # Remove networks
    docker network rm "zgdk-network-$WORKTREE_NAME" 2>/dev/null || echo "Network already removed"
else
    echo "No docker-compose.yml found, skipping Docker cleanup"
fi

cd - > /dev/null

# Step 2: Deallocate ports
echo -e "${GREEN}[2/6] Deallocating ports...${NC}"
if [ -f ".worktrees/scripts/manage-ports.py" ]; then
    python3 .worktrees/scripts/manage-ports.py deallocate "$WORKTREE_NAME" || echo "Port deallocation failed"
else
    echo "Port management script not found, manual cleanup may be needed"
fi

# Step 3: Remove git worktree
echo -e "${GREEN}[3/6] Removing git worktree...${NC}"
if git worktree list | grep -q "$WORKTREE_PATH"; then
    git worktree remove "$WORKTREE_PATH" --force
else
    echo "Worktree not found in git worktree list"
fi

# Step 4: Clean up any remaining files
echo -e "${GREEN}[4/6] Cleaning up remaining files...${NC}"
if [ -d "$WORKTREE_PATH" ]; then
    echo "Removing remaining directory: $WORKTREE_PATH"
    rm -rf "$WORKTREE_PATH"
fi

# Step 5: Prune git references
echo -e "${GREEN}[5/6] Pruning git references...${NC}"
git worktree prune
git gc --prune=now --quiet

# Step 6: Docker cleanup
echo -e "${GREEN}[6/6] Final Docker cleanup...${NC}"
# Remove any dangling containers/volumes related to this worktree
docker system prune -f --filter "label=com.docker.compose.project=zgdk$WORKTREE_NAME" 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ Worktree '$WORKTREE_NAME' removed successfully!${NC}"

# Show remaining worktrees
echo ""
echo "Remaining worktrees:"
git worktree list

# Show freed resources
echo ""
echo "Resources freed:"
echo "  - Docker containers: zgdk-*-$WORKTREE_NAME"
echo "  - Database: zgdk_$WORKTREE_NAME"  
echo "  - Directory: $WORKTREE_PATH"

EOF

chmod +x .worktrees/scripts/remove-worktree.sh
```

### Method 2: Manual Step-by-Step Removal
```bash
# 1. Navigate to worktree and stop containers
cd ../zgdk-your-feature
docker-compose down -v

# 2. Return to main repo
cd ../zgdk  # or wherever your main repo is

# 3. Remove the worktree
git worktree remove ../zgdk-your-feature --force

# 4. Clean up Docker resources
docker container rm zgdk-app-your-feature zgdk-db-your-feature 2>/dev/null || true
docker volume rm zgdk_postgres_data_your-feature 2>/dev/null || true
docker network rm zgdk-network-your-feature 2>/dev/null || true

# 5. Deallocate ports
python3 .worktrees/scripts/manage-ports.py deallocate your-feature

# 6. Prune git and Docker
git worktree prune
docker system prune -f
```

## Usage Examples

### Remove Completed Feature
```bash
# After your PR is merged
cd /path/to/main/repo
bash .worktrees/scripts/remove-worktree.sh feature-auth

# Or with force (skip confirmations)
bash .worktrees/scripts/remove-worktree.sh feature-auth --force
```

### Remove Failed/Abandoned Worktree
```bash
# For worktrees you no longer need
bash .worktrees/scripts/remove-worktree.sh experimental-feature --force
```

## Batch Removal

### Remove Multiple Worktrees
```bash
# Create batch removal script
cat > .worktrees/scripts/remove-multiple-worktrees.sh << 'EOF'
#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 <worktree1> <worktree2> ... [--force]"
    echo "Example: $0 feature-1 feature-2 old-experiment --force"
    exit 1
fi

# Check if last argument is --force
FORCE_FLAG=""
if [ "${@: -1}" = "--force" ]; then
    FORCE_FLAG="--force"
    set -- "${@:1:$(($#-1))}"  # Remove --force from arguments
fi

echo "Removing worktrees: $@"
echo "Force mode: ${FORCE_FLAG:-disabled}"

for WORKTREE in "$@"; do
    echo ""
    echo "Removing worktree: $WORKTREE"
    bash .worktrees/scripts/remove-worktree.sh "$WORKTREE" $FORCE_FLAG
done

echo ""
echo "Batch removal completed!"

EOF

chmod +x .worktrees/scripts/remove-multiple-worktrees.sh
```

### Remove All Inactive Worktrees
```bash
# Create script to remove worktrees older than N days
cat > .worktrees/scripts/cleanup-old-worktrees.sh << 'EOF'
#!/bin/bash

DAYS_OLD="${1:-30}"
FORCE_MODE="${2:-}"

echo "Finding worktrees older than $DAYS_OLD days..."

# Get all worktrees except main
WORKTREES=$(git worktree list --porcelain | grep "^worktree" | grep -v "$(pwd)" | cut -d' ' -f2)

if [ -z "$WORKTREES" ]; then
    echo "No additional worktrees found"
    exit 0
fi

OLD_WORKTREES=""

for WORKTREE_PATH in $WORKTREES; do
    if [ -d "$WORKTREE_PATH" ]; then
        # Get last modified time of worktree directory
        LAST_MODIFIED=$(stat -c %Y "$WORKTREE_PATH" 2>/dev/null || stat -f %m "$WORKTREE_PATH" 2>/dev/null)
        CURRENT_TIME=$(date +%s)
        DAYS_SINCE=$(( ($CURRENT_TIME - $LAST_MODIFIED) / 86400 ))
        
        if [ $DAYS_SINCE -gt $DAYS_OLD ]; then
            WORKTREE_NAME=$(basename "$WORKTREE_PATH" | sed 's/^zgdk-//')
            echo "Found old worktree: $WORKTREE_NAME ($DAYS_SINCE days old)"
            OLD_WORKTREES="$OLD_WORKTREES $WORKTREE_NAME"
        fi
    fi
done

if [ -z "$OLD_WORKTREES" ]; then
    echo "No old worktrees found"
    exit 0
fi

echo ""
echo "Old worktrees to remove:$OLD_WORKTREES"

if [ "$FORCE_MODE" != "--force" ]; then
    read -p "Remove these old worktrees? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cleanup cancelled"
        exit 1
    fi
fi

for WORKTREE_NAME in $OLD_WORKTREES; do
    echo "Removing old worktree: $WORKTREE_NAME"
    bash .worktrees/scripts/remove-worktree.sh "$WORKTREE_NAME" --force
done

echo "Old worktree cleanup completed!"

EOF

chmod +x .worktrees/scripts/cleanup-old-worktrees.sh
```

## Emergency Cleanup

### Force Remove Broken Worktree
```bash
# When normal removal fails
WORKTREE_NAME="broken-feature"

# Nuclear option - manual cleanup
echo "Force removing all traces of worktree: $WORKTREE_NAME"

# Stop and remove containers
docker stop "zgdk-app-$WORKTREE_NAME" "zgdk-db-$WORKTREE_NAME" 2>/dev/null || true
docker rm "zgdk-app-$WORKTREE_NAME" "zgdk-db-$WORKTREE_NAME" 2>/dev/null || true

# Remove volumes and networks
docker volume rm "zgdk_postgres_data_$WORKTREE_NAME" 2>/dev/null || true
docker network rm "zgdk-network-$WORKTREE_NAME" 2>/dev/null || true

# Remove directory
rm -rf "../zgdk-$WORKTREE_NAME"

# Clean git references
git worktree prune

# Deallocate ports
python3 .worktrees/scripts/manage-ports.py deallocate "$WORKTREE_NAME" 2>/dev/null || true

# Clean Docker system
docker system prune -f
```

### Repair Corrupted Worktree State
```bash
# If git worktree list shows invalid entries
git worktree list

# Remove invalid entries
git worktree prune

# If that doesn't work, manually edit git config
# (Advanced - be careful)
git config --list | grep worktree

# Remove specific worktree refs
git config --unset-all worktree.broken-path
```

## Verification and Monitoring

### Verify Complete Removal
```bash
# Create verification script
cat > .worktrees/scripts/verify-removal.sh << 'EOF'
#!/bin/bash

WORKTREE_NAME="$1"

if [ -z "$WORKTREE_NAME" ]; then
    echo "Usage: $0 <worktree-name>"
    exit 1
fi

echo "Verifying removal of worktree: $WORKTREE_NAME"
echo ""

# Check git worktree list
echo "Git worktree status:"
if git worktree list | grep -q "$WORKTREE_NAME"; then
    echo "❌ Still found in git worktree list"
else
    echo "✅ Not found in git worktree list"
fi

# Check directory
WORKTREE_PATH="../zgdk-$WORKTREE_NAME"
echo ""
echo "Directory status:"
if [ -d "$WORKTREE_PATH" ]; then
    echo "❌ Directory still exists: $WORKTREE_PATH"
else
    echo "✅ Directory removed: $WORKTREE_PATH"
fi

# Check Docker containers
echo ""
echo "Docker container status:"
CONTAINERS=$(docker ps -a --filter "name=zgdk.*$WORKTREE_NAME" --format "{{.Names}}")
if [ -n "$CONTAINERS" ]; then
    echo "❌ Found containers: $CONTAINERS"
else
    echo "✅ No containers found"
fi

# Check Docker volumes
echo ""
echo "Docker volume status:"
VOLUMES=$(docker volume ls --filter "name=.*$WORKTREE_NAME" --format "{{.Name}}")
if [ -n "$VOLUMES" ]; then
    echo "❌ Found volumes: $VOLUMES"
else
    echo "✅ No volumes found"
fi

# Check port allocation
echo ""
echo "Port allocation status:"
if [ -f ".worktrees/port-registry.json" ]; then
    if grep -q "$WORKTREE_NAME" .worktrees/port-registry.json; then
        echo "❌ Ports still allocated in registry"
    else
        echo "✅ No ports allocated in registry"
    fi
else
    echo "⚠️  Port registry file not found"
fi

echo ""
echo "Verification completed!"

EOF

chmod +x .worktrees/scripts/verify-removal.sh
```

### Monitor Worktree Usage
```bash
# Create monitoring script
cat > .worktrees/scripts/worktree-status.sh << 'EOF'
#!/bin/bash

echo "Worktree Status Report"
echo "====================="
echo ""

# List all worktrees
echo "Active Worktrees:"
git worktree list

echo ""

# Check Docker usage
echo "Docker Resources:"
echo "Containers:"
docker ps --filter "name=zgdk-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "Volumes:"
docker volume ls --filter "name=zgdk_" --format "table {{.Name}}\t{{.Size}}"

echo ""

# Port allocation status
if [ -f ".worktrees/port-registry.json" ]; then
    echo "Port Allocations:"
    python3 -c "
import json
with open('.worktrees/port-registry.json', 'r') as f:
    data = json.load(f)
for name, config in data.items():
    if name not in ['allocated_ports', 'next_available']:
        print(f'  {name}: App={config[\"app_port\"]}, DB={config[\"db_port\"]}')
"
else
    echo "Port registry not found"
fi

EOF

chmod +x .worktrees/scripts/worktree-status.sh
```

## Recovery and Troubleshooting

### Recover Accidentally Removed Worktree
```bash
# If you removed a worktree but the branch still exists
BRANCH_NAME="feature/your-feature"
WORKTREE_NAME="your-feature"

# Check if branch exists
git branch -a | grep "$BRANCH_NAME"

# If branch exists, recreate worktree
git worktree add "../zgdk-$WORKTREE_NAME" "$BRANCH_NAME"

# Reconfigure the worktree
cd "../zgdk-$WORKTREE_NAME"
bash .worktrees/scripts/create-worktree.sh "$WORKTREE_NAME" "$BRANCH_NAME"
```

### Clean Up Orphaned Docker Resources
```bash
# Find and remove orphaned resources
echo "Cleaning up orphaned Docker resources..."

# Remove containers with zgdk prefix that don't have corresponding worktrees
docker ps -a --filter "name=zgdk-" --format "{{.Names}}" | while read CONTAINER; do
    WORKTREE_SUFFIX=$(echo "$CONTAINER" | sed 's/zgdk-[^-]*-//')
    if [ ! -d "../zgdk-$WORKTREE_SUFFIX" ]; then
        echo "Removing orphaned container: $CONTAINER"
        docker rm -f "$CONTAINER"
    fi
done

# Remove volumes
docker volume ls --filter "name=zgdk_" --format "{{.Name}}" | while read VOLUME; do
    WORKTREE_SUFFIX=$(echo "$VOLUME" | sed 's/zgdk_postgres_data_//')
    if [ ! -d "../zgdk-$WORKTREE_SUFFIX" ]; then
        echo "Removing orphaned volume: $VOLUME"
        docker volume rm "$VOLUME"
    fi
done

# Remove networks
docker network ls --filter "name=zgdk-network-" --format "{{.Name}}" | while read NETWORK; do
    WORKTREE_SUFFIX=$(echo "$NETWORK" | sed 's/zgdk-network-//')
    if [ ! -d "../zgdk-$WORKTREE_SUFFIX" ]; then
        echo "Removing orphaned network: $NETWORK"
        docker network rm "$NETWORK"
    fi
done
```

### Fix Port Registry Corruption
```bash
# If port registry gets corrupted
echo "Backing up current port registry..."
cp .worktrees/port-registry.json .worktrees/port-registry.json.backup

# Rebuild port registry from active worktrees
cat > .worktrees/scripts/rebuild-port-registry.py << 'EOF'
#!/usr/bin/env python3
import json
import os
import glob

# Start with base structure
registry = {
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

# Find all worktree directories
worktree_dirs = glob.glob("../zgdk-*")
next_app_port = 8001
next_db_port = 5433

for worktree_dir in worktree_dirs:
    if os.path.isdir(worktree_dir):
        worktree_name = os.path.basename(worktree_dir).replace("zgdk-", "")
        
        # Try to read existing .env file to get ports
        env_file = os.path.join(worktree_dir, ".env")
        app_port = next_app_port
        db_port = next_db_port
        
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith("WORKTREE_PORT="):
                        app_port = int(line.split("=")[1].strip())
                    elif line.startswith("POSTGRES_PORT="):
                        db_port = int(line.split("=")[1].strip())
        
        registry[worktree_name] = {
            "app_port": app_port,
            "db_port": db_port,
            "prefix": "zgdk"
        }
        
        registry["allocated_ports"][str(app_port)] = worktree_name
        registry["allocated_ports"][str(db_port)] = worktree_name
        
        next_app_port = max(next_app_port, app_port + 1)
        next_db_port = max(next_db_port, db_port + 1)

registry["next_available"]["app_port"] = next_app_port
registry["next_available"]["db_port"] = next_db_port

# Save rebuilt registry
with open('.worktrees/port-registry.json', 'w') as f:
    json.dump(registry, f, indent=2)

print("Port registry rebuilt successfully!")

EOF

python3 .worktrees/scripts/rebuild-port-registry.py
```

## Best Practices

### Before Removal
- **Always push important work** to remote repository
- **Verify branch exists remotely** if you want to preserve it
- **Check for uncommitted changes** in the worktree
- **Stop Docker containers** before removal to prevent issues

### Safe Removal
- **Use the automated script** rather than manual commands
- **Verify removal** with the verification script
- **Keep main branch clean** by removing unused branches after worktree removal
- **Monitor Docker resources** to prevent accumulation of orphaned containers

### Cleanup Schedule
- **Weekly**: Review active worktrees and remove completed ones
- **Monthly**: Run cleanup of old worktrees (30+ days)
- **After PRs merge**: Remove corresponding worktrees immediately
- **Before system maintenance**: Clean up all unnecessary worktrees

## Important Notes

⚠️ **Permanent Deletion**: Worktree removal is permanent - ensure work is saved elsewhere

⚠️ **Docker Resources**: All associated containers, volumes, and networks are removed

⚠️ **Database Data**: Database contents in the worktree are permanently lost

⚠️ **Port Deallocation**: Ports are freed for reuse by other worktrees

⚠️ **Git References**: Local branch may be removed if not pushed to remote

⚠️ **Uncommitted Work**: Any uncommitted changes are permanently lost

⚠️ **Network Resources**: Docker networks specific to the worktree are removed