# Merge Worktree

## Overview
Merge changes from a worktree branch back into the main branch. This handles the complete workflow from testing to integration.

## Prerequisites
- Worktree development completed
- All tests passing in the worktree
- Code reviewed and approved
- No conflicts with main branch

## Safe Merge Process

### 1. Pre-Merge Verification
```bash
# In your worktree directory
cd ../zgdk-feature-name

# Ensure all changes are committed
git status
# Should show "working tree clean"

# Run final tests
docker-compose up --build
docker-compose logs app --tail=50 | grep -E "(ERROR|Failed)"

# Check for any Docker issues
docker-compose ps
```

### 2. Sync with Main Branch
```bash
# Fetch latest changes from main
git fetch origin main

# Check for conflicts before merging
git merge-base HEAD origin/main
git diff $(git merge-base HEAD origin/main)..HEAD --name-only

# If conflicts exist, rebase first
git rebase origin/main
# Resolve any conflicts, then continue
git rebase --continue
```

### 3. Switch to Main and Merge
```bash
# Navigate back to main repository
cd ../zgdk

# Ensure main is clean and up to date
git checkout main
git pull origin main

# Merge the feature branch
git merge feature-name --no-ff
# The --no-ff creates a merge commit preserving branch history
```

## Automated Merge Script

### Create Merge Helper
```bash
cat > .worktrees/scripts/merge-worktree.sh << 'EOF'
#!/bin/bash

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <worktree-name> [--fast-forward|--no-ff|--squash]"
    echo "Example: $0 feature-auth --no-ff"
    exit 1
fi

WORKTREE_NAME="$1"
MERGE_TYPE="${2:---no-ff}"

WORKTREE_PATH="../zgdk-$WORKTREE_NAME"
BRANCH_NAME=$(cd "$WORKTREE_PATH" && git branch --show-current)

echo "Merging worktree: $WORKTREE_NAME"
echo "Branch: $BRANCH_NAME"
echo "Merge type: $MERGE_TYPE"

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    echo "Error: Worktree $WORKTREE_PATH does not exist"
    exit 1
fi

# Verify worktree is clean
cd "$WORKTREE_PATH"
if [ -n "$(git status --porcelain)" ]; then
    echo "Error: Worktree has uncommitted changes"
    git status
    exit 1
fi

echo "Running final tests in worktree..."
if ! docker-compose up --build -d; then
    echo "Error: Docker build failed"
    exit 1
fi

# Wait for container to start
sleep 5

# Check for errors
if docker-compose logs app --tail=50 | grep -E "(ERROR|Failed)" > /dev/null; then
    echo "Error: Application has errors"
    docker-compose logs app --tail=50 | grep -E "(ERROR|Failed)"
    docker-compose down
    exit 1
fi

docker-compose down
echo "✅ Tests passed"

# Sync with main
echo "Syncing with main branch..."
git fetch origin main

# Check for conflicts
if ! git merge-base --is-ancestor origin/main HEAD; then
    echo "Branch is behind main, attempting rebase..."
    if ! git rebase origin/main; then
        echo "Error: Rebase failed. Please resolve conflicts manually."
        echo "After resolving conflicts, run:"
        echo "  git rebase --continue"
        echo "  bash .worktrees/scripts/merge-worktree.sh $WORKTREE_NAME $MERGE_TYPE"
        exit 1
    fi
fi

# Switch to main repository
cd ../zgdk

# Ensure main is up to date
echo "Updating main branch..."
git checkout main
git pull origin main

# Perform the merge
echo "Merging $BRANCH_NAME into main..."
case $MERGE_TYPE in
    --fast-forward)
        git merge "$BRANCH_NAME" --ff-only
        ;;
    --no-ff)
        git merge "$BRANCH_NAME" --no-ff -m "Merge branch '$BRANCH_NAME'

Features and changes from worktree: $WORKTREE_NAME
        
🤖 Generated with Claude Code"
        ;;
    --squash)
        git merge "$BRANCH_NAME" --squash
        git commit -m "$(git log $BRANCH_NAME --oneline | head -1 | cut -d' ' -f2-)

Squashed merge of $BRANCH_NAME from worktree: $WORKTREE_NAME

🤖 Generated with Claude Code"
        ;;
    *)
        echo "Error: Unknown merge type $MERGE_TYPE"
        exit 1
        ;;
esac

echo ""
echo "✅ Merge completed successfully!"
echo ""
echo "Next steps:"
echo "1. Test the merged changes: docker-compose up --build"
echo "2. Push to remote: git push origin main"
echo "3. Remove worktree: bash .worktrees/scripts/remove-worktree.sh $WORKTREE_NAME"

EOF

chmod +x .worktrees/scripts/merge-worktree.sh
```

## Merge Types

### No-Fast-Forward Merge (Recommended)
```bash
# Preserves branch history with merge commit
bash .worktrees/scripts/merge-worktree.sh feature-auth --no-ff
```

### Fast-Forward Merge
```bash
# Linear history, only when no conflicts
bash .worktrees/scripts/merge-worktree.sh feature-auth --fast-forward
```

### Squash Merge
```bash
# Combines all commits into single commit
bash .worktrees/scripts/merge-worktree.sh feature-auth --squash
```

## Manual Merge Process

### Step-by-Step Manual Merge
```bash
# 1. Final verification in worktree
cd ../zgdk-feature-auth
git status  # Should be clean
docker-compose up --build  # Final test

# 2. Sync with main
git fetch origin main
git rebase origin/main  # Resolve conflicts if any

# 3. Switch to main
cd ../zgdk
git checkout main
git pull origin main

# 4. Merge (choose one)
git merge feature/auth-system --no-ff  # Recommended
# OR
git merge feature/auth-system --ff-only  # Fast-forward only
# OR  
git merge feature/auth-system --squash  # Squash commits

# 5. Push changes
git push origin main
```

## Conflict Resolution

### If Rebase Conflicts Occur
```bash
# In the worktree directory
git status  # Shows conflicted files

# Edit conflicted files, then:
git add <resolved-files>
git rebase --continue

# If rebase becomes too complex:
git rebase --abort
# Then try merge instead of rebase in main
```

### If Merge Conflicts Occur
```bash
# In main repository
git status  # Shows conflicted files

# Resolve conflicts, then:
git add <resolved-files>
git commit

# Or abort the merge:
git merge --abort
```

## Post-Merge Verification

### Verify Merge Success
```bash
# In main repository
git log --oneline -10  # Check commit history
git diff HEAD~1..HEAD  # Review merged changes

# Test the merged code
docker-compose up --build
docker-compose logs app --tail=50 | grep -E "(ERROR|Failed)"
```

### Cleanup After Successful Merge
```bash
# Remove the worktree (optional, can keep for reference)
bash .worktrees/scripts/remove-worktree.sh feature-auth

# Delete remote branch if pushed
git push origin --delete feature/auth-system
```

## Best Practices

### Before Merging
- ✅ All tests pass in worktree
- ✅ Code reviewed and approved  
- ✅ Feature is complete and documented
- ✅ No uncommitted changes
- ✅ Synced with latest main

### Merge Strategy
- **--no-ff**: Use for feature branches (preserves history)
- **--ff-only**: Use for hotfixes (clean linear history)
- **--squash**: Use for experimental branches (clean single commit)

### After Merging
- ✅ Test merged code in main
- ✅ Push to remote repository
- ✅ Update issue/ticket status
- ✅ Clean up worktree if no longer needed

## Troubleshooting

### Merge Script Fails
```bash
# Check Docker status
docker-compose ps
docker-compose logs app

# Check git status
git status
git log --oneline -5

# Manual recovery
git reset --hard HEAD~1  # Undo failed merge
```

### Branch Behind Main
```bash
# In worktree
git fetch origin main
git rebase origin/main

# Or merge main into feature branch
git merge origin/main
```

### Large Conflicts
```bash
# Use merge tool
git mergetool

# Or reset and use different strategy
git merge --abort
git merge origin/main --strategy-option=ours
```

## Important Notes

⚠️ **Always test before merging**: Run full test suite in worktree
⚠️ **Backup important changes**: Consider creating backup branch
⚠️ **Review merge commits**: Use descriptive merge commit messages
⚠️ **Clean workspace**: Ensure no uncommitted changes before merge