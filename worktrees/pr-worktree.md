# Create Pull Request from Worktree

## Overview
Create and manage pull requests from git worktrees, ensuring proper testing, branch cleanup, and code review workflow for the Discord bot project.

## Prerequisites
- Worktree created and configured (`@worktrees/create-worktree.md`)
- Changes committed to worktree branch
- Docker containers tested and working
- GitHub CLI installed (`gh`) or web access

## Pre-PR Checklist

### 1. Test Your Changes
```bash
# Navigate to your worktree
cd ../zgdk-your-feature

# Ensure containers are running
docker-compose up --build -d

# Check for errors in logs
docker-compose logs app --tail=100 | grep -E "(ERROR|Failed)"

# Run any tests if available
docker-compose exec app python -m pytest || echo "No pytest found"

# Test bot functionality manually
docker-compose logs app --follow --tail=20
```

### 2. Verify Code Quality
```bash
# Check for obvious issues
grep -r "TODO\|FIXME\|HACK" . --include="*.py" || echo "No TODOs found"

# Ensure no sensitive data in commits
git log --oneline -10
git show --name-only

# Check for merge conflicts with main
git fetch origin
git merge-base HEAD origin/main
git diff origin/main...HEAD --name-only
```

## Creating Pull Request

### Method 1: GitHub CLI (Recommended)
```bash
# Ensure you're in the worktree directory
cd ../zgdk-your-feature

# Push branch to origin (if not already pushed)
git push -u origin $(git branch --show-current)

# Create PR with GitHub CLI
gh pr create --title "feat: your feature description" \
             --body "$(cat << 'EOF'
## Description
Brief description of changes made.

## Changes Made
- [ ] Feature 1 implemented
- [ ] Feature 2 updated  
- [ ] Tests added/updated
- [ ] Docker tested

## Testing Done
- [ ] Docker containers start successfully
- [ ] No errors in application logs
- [ ] Bot connects to Discord
- [ ] Feature works as expected

## Worktree Info
Created from worktree: $(basename $(pwd))
Database: zgdk_$(basename $(pwd))
Ports: App $(grep WORKTREE_PORT .env | cut -d= -f2), DB $(grep POSTGRES_PORT .env | cut -d= -f2)
EOF
)" \
             --assignee @me \
             --draft
```

### Method 2: Automated PR Script
```bash
# Create automated PR creation script
cat > .worktrees/scripts/create-pr.sh << 'EOF'
#!/bin/bash

set -e

# Check if we're in a worktree
if [ ! -f ".worktree-config.env" ] && [ ! -f ".env" ]; then
    echo "Error: This doesn't appear to be a worktree directory"
    echo "Expected to find .env or .worktree-config.env file"
    exit 1
fi

WORKTREE_NAME=$(basename $(pwd))
CURRENT_BRANCH=$(git branch --show-current)

echo "Creating PR for worktree: $WORKTREE_NAME"
echo "Branch: $CURRENT_BRANCH"

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is required for automated PR creation"
    echo "Install with: curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
    echo "Or create PR manually on GitHub"
    exit 1
fi

# Ensure we're authenticated
if ! gh auth status &> /dev/null; then
    echo "Please authenticate with GitHub CLI first:"
    echo "gh auth login"
    exit 1
fi

# Get worktree configuration
APP_PORT=$(grep -E "WORKTREE_PORT|APP_PORT" .env | cut -d= -f2 | head -1)
DB_PORT=$(grep "POSTGRES_PORT" .env | cut -d= -f2)

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Warning: You have uncommitted changes"
    echo "Commit them first or they won't be included in the PR"
    git status --short
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Push branch if not already pushed
if ! git ls-remote --exit-code --heads origin "$CURRENT_BRANCH" &>/dev/null; then
    echo "Pushing branch to origin..."
    git push -u origin "$CURRENT_BRANCH"
else
    echo "Branch already exists on origin, pushing latest changes..."
    git push
fi

# Get commit messages for PR description
COMMITS=$(git log --oneline origin/main..HEAD | head -5)

# Create PR body
PR_BODY=$(cat << PREOF
## Description
Changes implemented in worktree \`$WORKTREE_NAME\`.

## Recent Commits
\`\`\`
$COMMITS
\`\`\`

## Testing Checklist
- [ ] Docker containers start successfully (\`docker-compose up --build\`)
- [ ] No errors in application logs (\`docker-compose logs app --tail=100 | grep -E "(ERROR|Failed)"\`)
- [ ] Bot connects to Discord successfully
- [ ] New features work as expected
- [ ] No regression in existing functionality

## Worktree Details
- **Worktree**: $WORKTREE_NAME
- **Database**: zgdk_$WORKTREE_NAME  
- **App Port**: $APP_PORT
- **DB Port**: $DB_PORT

## Review Notes
This PR was created from a git worktree with isolated Docker containers and database.
PREOF
)

# Prompt for PR title
echo "Enter PR title (or press Enter for default):"
read -p "Title: " PR_TITLE

if [ -z "$PR_TITLE" ]; then
    # Generate title from branch name
    PR_TITLE=$(echo "$CURRENT_BRANCH" | sed 's|.*/||' | sed 's|-| |g' | sed 's/^/feat: /')
fi

echo "Creating PR with title: $PR_TITLE"

# Create the PR
PR_URL=$(gh pr create \
    --title "$PR_TITLE" \
    --body "$PR_BODY" \
    --assignee @me \
    --draft)

echo ""
echo "✅ Pull Request created successfully!"
echo "URL: $PR_URL"
echo ""
echo "Next steps:"
echo "1. Review the PR description and edit if needed"
echo "2. Request reviews from team members"
echo "3. Mark as ready for review when done"
echo "4. After merge, clean up with: bash .worktrees/scripts/remove-worktree.sh $WORKTREE_NAME"

EOF

chmod +x .worktrees/scripts/create-pr.sh
```

## Usage Examples

### Quick PR Creation
```bash
# From your worktree directory
cd ../zgdk-feature-auth

# Create PR (will prompt for title)
bash .worktrees/scripts/create-pr.sh
```

### Manual PR with Custom Details
```bash
# Push your branch
git push -u origin feature/auth-system

# Create detailed PR
gh pr create --title "feat: implement user authentication system" \
             --body "Implements JWT-based authentication with role management" \
             --label "enhancement" \
             --milestone "v2.0" \
             --assignee username
```

## PR Management

### Update PR with New Changes
```bash
# Make additional commits in your worktree
git add .
git commit -m "fix: address review feedback"

# Push updates
git push

# PR automatically updates - add comment about changes
gh pr comment --body "Updated PR with review feedback:
- Fixed authentication flow
- Added error handling  
- Updated tests"
```

### Handle Merge Conflicts
```bash
# Sync with main branch
git fetch origin
git merge origin/main

# If conflicts occur, resolve them
git status
# Edit conflicted files
git add .
git commit -m "resolve: merge conflicts with main"

# Push resolved conflicts
git push
```

## Advanced PR Workflows

### Auto-populate PR from Commits
```bash
# Create script for smart PR creation
cat > .worktrees/scripts/smart-pr.sh << 'EOF'
#!/bin/bash

set -e

WORKTREE_NAME=$(basename $(pwd))
CURRENT_BRANCH=$(git branch --show-current)

# Get all commits since main
COMMITS=$(git log --oneline origin/main..HEAD)
COMMIT_COUNT=$(echo "$COMMITS" | wc -l)

# Generate title from first commit or branch name
FIRST_COMMIT=$(echo "$COMMITS" | tail -1 | cut -d' ' -f2-)
if [ -n "$FIRST_COMMIT" ]; then
    PR_TITLE="$FIRST_COMMIT"
else
    PR_TITLE=$(echo "$CURRENT_BRANCH" | sed 's|.*/||' | sed 's|-| |g')
fi

# Generate detailed description
PR_BODY=$(cat << PREOF
## Summary
$COMMIT_COUNT commits implementing changes in the \`$WORKTREE_NAME\` worktree.

## Changes Made
$(echo "$COMMITS" | sed 's/^[a-f0-9]* /- /')

## Files Modified
$(git diff --name-only origin/main..HEAD | sed 's/^/- /')

## Testing
Tested in isolated worktree environment:
- Database: \`zgdk_$WORKTREE_NAME\`
- Docker containers: \`zgdk-*-$WORKTREE_NAME\`
- No conflicts with main development

## Deployment Notes
This feature was developed in isolation and should merge cleanly.
PREOF
)

gh pr create --title "$PR_TITLE" --body "$PR_BODY" --draft --assignee @me

EOF

chmod +x .worktrees/scripts/smart-pr.sh
```

## PR Checklist Template

### Before Creating PR
- [ ] All changes committed and pushed
- [ ] Docker containers start without errors
- [ ] Application logs are clean (no ERROR/Failed messages)  
- [ ] Bot functionality tested manually
- [ ] No TODO/FIXME comments left in code
- [ ] No sensitive data in commits
- [ ] Branch is up to date with main

### PR Description Should Include
- [ ] Clear description of changes
- [ ] List of modified files/features
- [ ] Testing methodology
- [ ] Worktree configuration details
- [ ] Any breaking changes noted

### After PR Creation
- [ ] Review PR description for accuracy
- [ ] Add appropriate labels and milestone
- [ ] Request reviews from team members
- [ ] Respond to review feedback promptly
- [ ] Keep PR updated with main branch

## Troubleshooting

### Push Rejected
```bash
# Branch might be protected or you lack permissions
git push -u origin feature-branch

# If rejected, check branch protection rules
gh api repos/:owner/:repo/branches/main/protection
```

### PR Creation Fails
```bash
# Check GitHub CLI authentication
gh auth status

# Re-authenticate if needed
gh auth login

# Check repository permissions
gh repo view
```

### Merge Conflicts in PR
```bash
# Fetch latest main
git fetch origin

# Merge main into your branch (preferred over rebase for worktrees)
git merge origin/main

# Resolve conflicts manually
git status
# Edit files, then:
git add .
git commit -m "resolve: merge conflicts with main"
git push
```

### Large PR Size
```bash
# Check PR size
gh pr diff | wc -l

# If too large, consider splitting:
# 1. Create new branch from current state
git checkout -b feature/part-2

# 2. Reset original branch to earlier commit
git checkout feature/original
git reset --hard <earlier-commit>

# 3. Create smaller PR, then continue with part-2
```

## Best Practices

### PR Title Conventions
- `feat:` for new features
- `fix:` for bug fixes  
- `refactor:` for code restructuring
- `docs:` for documentation
- `test:` for test additions
- `chore:` for maintenance tasks

### PR Size Guidelines
- Keep PRs focused on single feature/fix
- Aim for < 400 lines of changes when possible
- Split large features into multiple PRs
- Include tests and documentation in same PR as feature

### Review Process
- Self-review your PR before requesting others
- Include screenshots for UI changes
- Respond to feedback within 24 hours
- Keep discussions focused and professional

## Important Notes

⚠️ **Database Isolation**: Your PR includes changes tested against an isolated database (`zgdk_<worktree-name>`)

⚠️ **Docker Testing**: Ensure your changes work in the Docker environment, not just local development

⚠️ **Port Conflicts**: Your worktree uses different ports - mention this in PR if relevant to testing

⚠️ **Cleanup**: After PR is merged, clean up the worktree using `@worktrees/remove-worktree.md`

⚠️ **Sensitive Data**: Double-check that no tokens, passwords, or secrets are included in commits