# GitHub Actions Configuration

## Required Secrets

Before the CI/CD pipeline can work, you need to add the following secrets to your GitHub repository:

1. **DOCKER_PASSWORD** - Your Docker Hub access token (REQUIRED)
   - Go to GitHub repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `DOCKER_PASSWORD`
   - Value: Your Docker Hub token (not your password)

2. **CODECOV_TOKEN** - Token for code coverage reports (OPTIONAL)
   - Get token from https://codecov.io
   - Add as repository secret
   - Name: `CODECOV_TOKEN`
   - Value: Your Codecov token

## CI/CD Pipeline

The pipeline consists of the following jobs:

### 1. Test
- Runs on every push and PR
- Executes Python tests with pytest
- Generates code coverage report

### 2. Build and Push
- Runs only on push to `main` or `develop` branches
- Builds multi-platform Docker images (amd64, arm64)
- Pushes to Docker Hub with tags:
  - `latest` (for main branch)
  - `main-<short-sha>` (for main branch)
  - `develop-<short-sha>` (for develop branch)

### 3. Update Helm Values
- Runs only after successful build on `main` branch
- Updates the image tag in `helm/zgdk/values.yaml`
- Commits the change back to the repository
- This triggers ArgoCD to deploy the new version

### 4. Helm Lint
- Validates Helm chart syntax
- Ensures chart can be rendered properly

## Image Tagging Strategy

- **main branch**: `ppyzel/zgdk:latest` and `ppyzel/zgdk:main-<sha>`
- **develop branch**: `ppyzel/zgdk:develop-<sha>`
- **feature branches**: Build and test only, no push

## ArgoCD Integration

ArgoCD watches the `helm/zgdk/values.yaml` file. When the image tag is updated by the pipeline, ArgoCD automatically:
1. Detects the change
2. Syncs the new image to Kubernetes
3. Performs a rolling update