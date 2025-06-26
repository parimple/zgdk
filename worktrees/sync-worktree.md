# Sync Worktree with Main Branch

## Overview
Keep your git worktrees synchronized with the main branch to prevent merge conflicts and ensure you're working with the latest codebase changes.

## Prerequisites
- Active worktree with ongoing development
- Access to main repository
- Docker containers properly configured
- Understanding of Git merge vs rebase workflows

## Sync Strategies

### Strategy 1: Merge Main (Recommended for Worktrees)
```bash
# Navigate to your worktree
cd ../zgdk-your-feature

# Fetch latest changes from remote
git fetch origin

# Merge main into your feature branch
git merge origin/main
```

### Strategy 2: Rebase on Main (Use with Caution)
```bash
# Only use rebase if you haven't shared your branch yet
git fetch origin
git rebase origin/main

# If conflicts occur during rebase:
# 1. Resolve conflicts in files
# 2. git add .
# 3. git rebase --continue
```

## Automated Sync Script

### Create Sync Helper
```bash
# Create automated sync script
cat > .worktrees/scripts/sync-worktree.sh << 'EOF'
#!/bin/bash

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in a worktree
if [ ! -f ".worktree-config.env" ] && [ ! -f ".env" ]; then
    echo -e "${RED}Error: This doesn't appear to be a worktree directory${NC}"
    echo "Expected to find .env or .worktree-config.env file"
    exit 1
fi

WORKTREE_NAME=$(basename $(pwd))
CURRENT_BRANCH=$(git branch --show-current)
MAIN_BRANCH="${1:-main}"

echo -e "${GREEN}Syncing worktree: $WORKTREE_NAME${NC}"
echo -e "${GREEN}Current branch: $CURRENT_BRANCH${NC}"
echo -e "${GREEN}Target branch: $MAIN_BRANCH${NC}"

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${YELLOW}Warning: You have uncommitted changes${NC}"
    git status --short
    echo ""
    read -p "Stash changes and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stashing changes..."
        git stash push -m "Auto-stash before sync $(date)"
        STASHED=true
    else
        echo "Please commit or stash your changes first"
        exit 1
    fi
fi

# Check if Docker containers are running
if docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}Docker containers are running. Stopping them during sync...${NC}"
    docker-compose down
    RESTART_DOCKER=true
fi

echo "Fetching latest changes from origin..."
git fetch origin

# Check if main branch exists
if ! git show-ref --verify --quiet "refs/remotes/origin/$MAIN_BRANCH"; then
    echo -e "${RED}Error: Branch 'origin/$MAIN_BRANCH' not found${NC}"
    echo "Available branches:"
    git branch -r
    exit 1
fi

# Get current commit and main commit for comparison
CURRENT_COMMIT=$(git rev-parse HEAD)
MAIN_COMMIT=$(git rev-parse "origin/$MAIN_BRANCH")

if [ "$CURRENT_COMMIT" = "$MAIN_COMMIT" ]; then
    echo -e "${GREEN}Already up to date with $MAIN_BRANCH${NC}"
else
    # Check if there are conflicts before merging
    echo "Checking for potential conflicts..."
    
    # Get the merge base
    MERGE_BASE=$(git merge-base HEAD "origin/$MAIN_BRANCH")
    
    # Show what will be merged
    echo -e "${YELLOW}Changes in $MAIN_BRANCH since your branch diverged:${NC}"
    git log --oneline "$MERGE_BASE..origin/$MAIN_BRANCH" | head -10
    
    echo ""
    echo -e "${YELLOW}Your changes since diverging from $MAIN_BRANCH:${NC}"
    git log --oneline "$MERGE_BASE..HEAD" | head -10
    
    echo ""
    read -p "Continue with merge? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Sync cancelled"
        exit 1
    fi
    
    echo "Merging origin/$MAIN_BRANCH into $CURRENT_BRANCH..."
    if git merge "origin/$MAIN_BRANCH" --no-edit; then
        echo -e "${GREEN}✅ Merge completed successfully${NC}"
    else
        echo -e "${RED}❌ Merge conflicts detected${NC}"
        echo ""
        echo "Conflicts in files:"
        git diff --name-only --diff-filter=U
        echo ""
        echo "To resolve:"
        echo "1. Edit the conflicted files"
        echo "2. Run: git add ."
        echo "3. Run: git commit"
        echo "4. Run this script again to complete sync"
        exit 1
    fi
fi

# Restore stashed changes if any
if [ "$STASHED" = true ]; then
    echo "Restoring stashed changes..."
    if git stash pop; then
        echo -e "${GREEN}Stashed changes restored${NC}"
    else
        echo -e "${YELLOW}Stash pop had conflicts. Check 'git status'${NC}"
    fi
fi

# Update Docker configuration if needed
echo "Checking if Docker configuration needs updates..."

# Check if main branch has updated docker-compose or requirements
DOCKER_CHANGES=$(git diff HEAD~1 --name-only | grep -E "(docker-compose|Dockerfile|requirements)" || true)
if [ -n "$DOCKER_CHANGES" ]; then
    echo -e "${YELLOW}Docker-related files changed. You may need to rebuild containers.${NC}"
    echo "Changed files:"
    echo "$DOCKER_CHANGES"
    REBUILD_NEEDED=true
fi

# Restart Docker containers if they were running
if [ "$RESTART_DOCKER" = true ]; then
    echo "Restarting Docker containers..."
    if [ "$REBUILD_NEEDED" = true ]; then
        echo "Rebuilding due to Docker file changes..."
        docker-compose up --build -d
    else
        docker-compose up -d
    fi
    
    # Wait a moment and check if containers started successfully
    sleep 5
    if docker-compose ps | grep -q "Up"; then
        echo -e "${GREEN}✅ Docker containers restarted successfully${NC}"
        
        # Check for errors in logs
        echo "Checking application logs for errors..."
        ERRORS=$(docker-compose logs app --tail=50 | grep -i "error\|failed\|exception" | head -5 || true)
        if [ -n "$ERRORS" ]; then
            echo -e "${RED}⚠️  Found errors in application logs:${NC}"
            echo "$ERRORS"
        else
            echo -e "${GREEN}No errors found in application logs${NC}"
        fi
    else
        echo -e "${RED}⚠️  Docker containers failed to start properly${NC}"
        docker-compose ps
    fi
fi

echo ""
echo -e "${GREEN}✅ Worktree sync completed!${NC}"
echo ""
echo "Summary:"
echo "- Worktree: $WORKTREE_NAME"
echo "- Branch: $CURRENT_BRANCH"  
echo "- Synced with: origin/$MAIN_BRANCH"
echo "- Current commit: $(git rev-parse --short HEAD)"

if [ "$REBUILD_NEEDED" = true ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Docker files changed - containers were rebuilt${NC}"
    echo "Test your application to ensure everything works correctly"
fi

EOF

chmod +x .worktrees/scripts/sync-worktree.sh
```

## Sync Workflows

### Daily Sync (Recommended)
```bash
# Run this daily to stay up to date
cd ../zgdk-your-feature
bash .worktrees/scripts/sync-worktree.sh

# Or manually:
git fetch origin
git merge origin/main
docker-compose up --build -d
```

### Before Major Changes
```bash
# Sync before starting significant work
git fetch origin
git log --oneline HEAD..origin/main  # See what you'll be merging

# If many changes, consider syncing frequently
git merge origin/main
```

### Before Creating PR
```bash
# Always sync before creating PR to minimize conflicts
bash .worktrees/scripts/sync-worktree.sh
git push  # Push the merged changes
```

## Handling Conflicts

### Merge Conflicts Resolution
```bash
# When conflicts occur during sync
git status  # See conflicted files

# Edit each conflicted file, looking for:
# <<<<<<< HEAD
# Your changes
# =======
# Main branch changes  
# >>>>>>> origin/main

# After resolving all conflicts:
git add .
git commit -m "resolve: merge conflicts with main"

# Continue with normal development
```

### Docker Configuration Conflicts
```bash
# If docker-compose.yml conflicts during sync
git status

# Usually keep your worktree version (it has unique ports/names)
# But check for important updates from main
git show HEAD~1:docker-compose.yml  # See main's version
git show HEAD:docker-compose.yml    # See your version

# Resolve manually and rebuild
docker-compose down
docker-compose up --build
```

### Database Schema Conflicts
```bash
# If database migrations conflict
docker-compose down -v  # Remove volumes to reset DB
docker-compose up --build

# Re-run any database migrations
docker-compose exec app python manage.py migrate  # If Django
# Or whatever migration command your bot uses
```

## Advanced Sync Scenarios

### Sync Multiple Worktrees
```bash
# Create script to sync all worktrees
cat > .worktrees/scripts/sync-all-worktrees.sh << 'EOF'
#!/bin/bash

set -e

echo "Finding all worktrees..."
WORKTREES=$(git worktree list | grep -v "$(pwd)" | awk '{print $1}')

if [ -z "$WORKTREES" ]; then
    echo "No additional worktrees found"
    exit 0
fi

echo "Found worktrees:"
echo "$WORKTREES"
echo ""

for WORKTREE_PATH in $WORKTREES; do
    if [ -d "$WORKTREE_PATH" ]; then
        echo "Syncing worktree: $WORKTREE_PATH"
        cd "$WORKTREE_PATH"
        
        # Use the sync script if available
        if [ -f ".worktrees/scripts/sync-worktree.sh" ]; then
            bash .worktrees/scripts/sync-worktree.sh
        else
            # Fallback to manual sync
            git fetch origin
            git merge origin/main --no-edit
        fi
        
        echo "Completed: $WORKTREE_PATH"
        echo "---"
    fi
done

echo "All worktrees synced!"

EOF

chmod +x .worktrees/scripts/sync-all-worktrees.sh
```

### Selective File Sync
```bash
# Sometimes you want specific files from main without full merge
git fetch origin

# Get specific file from main
git checkout origin/main -- path/to/specific/file.py

# Or get specific directory
git checkout origin/main -- cogs/events/

# Commit the selective updates
git add .
git commit -m "sync: update specific files from main"
```

### Sync with Rebase (Advanced)
```bash
# Only use if you understand Git rebase and branch hasn't been shared
git fetch origin

# Interactive rebase to clean up commits
git rebase -i origin/main

# Or automatic rebase
git rebase origin/main

# If conflicts during rebase:
# 1. Resolve conflicts
# 2. git add .
# 3. git rebase --continue
```

## Sync Monitoring

### Check Sync Status
```bash
# Create status checking script
cat > .worktrees/scripts/check-sync-status.sh << 'EOF'
#!/bin/bash

WORKTREE_NAME=$(basename $(pwd))
CURRENT_BRANCH=$(git branch --show-current)

echo "Worktree: $WORKTREE_NAME"
echo "Branch: $CURRENT_BRANCH"
echo ""

# Fetch to get latest remote info
git fetch origin

# Check how far behind/ahead we are
BEHIND=$(git rev-list --count HEAD..origin/main)
AHEAD=$(git rev-list --count origin/main..HEAD)

echo "Status relative to main:"
echo "  Behind: $BEHIND commits"
echo "  Ahead: $AHEAD commits"

if [ $BEHIND -gt 0 ]; then
    echo ""
    echo "Commits you're missing from main:"
    git log --oneline HEAD..origin/main | head -5
fi

if [ $AHEAD -gt 0 ]; then
    echo ""
    echo "Your commits not in main:"
    git log --oneline origin/main..HEAD | head -5
fi

# Check for potential conflicts
if [ $BEHIND -gt 0 ] && [ $AHEAD -gt 0 ]; then
    echo ""
    echo "⚠️  You have diverged from main. Consider syncing soon."
fi

EOF

chmod +x .worktrees/scripts/check-sync-status.sh
```

### Automated Sync Reminders
```bash
# Add to your shell profile (.bashrc, .zshrc) for reminders
cat >> ~/.bashrc << 'EOF'

# Worktree sync reminder
check_worktree_sync() {
    if [ -f ".env" ] && [ -f ".worktree-config.env" ]; then
        LAST_SYNC=$(git log -1 --grep="Merge.*origin/main" --format="%ct" 2>/dev/null || echo 0)
        CURRENT_TIME=$(date +%s)
        DAYS_SINCE=$((($CURRENT_TIME - $LAST_SYNC) / 86400))
        
        if [ $DAYS_SINCE -gt 3 ]; then
            echo "⚠️  Worktree hasn't synced with main in $DAYS_SINCE days"
            echo "Consider running: bash .worktrees/scripts/sync-worktree.sh"
        fi
    fi
}

# Run check when entering directories
cd() {
    builtin cd "$@"
    check_worktree_sync
}

EOF
```

## Troubleshooting

### Sync Fails with Docker Issues
```bash
# Stop all containers first
docker-compose down

# Remove any conflicting networks/volumes if needed
docker network prune
docker volume prune

# Sync without Docker running
git fetch origin
git merge origin/main

# Restart with fresh build
docker-compose up --build
```

### Cannot Merge Due to Uncommitted Changes
```bash
# Stash your changes
git stash push -m "Work in progress before sync"

# Sync with main
git merge origin/main

# Restore your changes
git stash pop

# Resolve any conflicts between your stashed work and merged changes
```

### Merge Conflicts in Generated Files
```bash
# For files like docker-compose.yml that are generated per worktree
git checkout --ours docker-compose.yml  # Keep your version
git checkout --theirs some-shared-file.py  # Take main's version

# Add resolved files
git add .
git commit -m "resolve: merge conflicts, kept worktree-specific configs"
```

### Lost Commits After Sync
```bash
# Check reflog to find lost commits
git reflog

# Recovery lost commits
git cherry-pick <lost-commit-hash>

# Or reset to before sync if needed
git reset --hard HEAD@{n}  # where n is the reflog entry
```

## Best Practices

### Sync Frequency
- **Daily**: For active development
- **Before major changes**: To avoid large conflicts  
- **Before PR creation**: To ensure clean merge
- **After long breaks**: To catch up with team changes

### Conflict Resolution
- **Prefer merge over rebase** for worktrees (preserves context)
- **Keep worktree-specific configs** (docker-compose.yml, .env)
- **Take main's version** for shared code files when in doubt
- **Test after every sync** to ensure functionality

### Docker Considerations
- **Always rebuild** after syncing if Docker files changed
- **Check logs** after restart to ensure no errors
- **Reset database** if schema migrations conflict
- **Update ports** if main branch changes port allocation

## Important Notes

⚠️ **Backup Before Sync**: Always commit your work before syncing

⚠️ **Docker Restart**: Containers may need rebuilding after sync

⚠️ **Database Changes**: Schema changes in main may require database reset

⚠️ **Port Conflicts**: Sync may introduce port conflicts - check docker-compose.yml

⚠️ **Conflict Resolution**: Take time to understand conflicts rather than blindly accepting changes

⚠️ **Test After Sync**: Always test your application after syncing to ensure it still works