#!/bin/sh
set -e

# Configuration
NAMESPACE="zgdk"
DEPLOYMENT="zgdk-discord-bot"
CONTAINER="bot"
REGISTRY="docker.io"
IMAGE="ppyzel/zgdk"
TAG_PATTERN="main-"

echo "Checking for new image updates..."

# Get current image
CURRENT_IMAGE=$(kubectl get deployment ${DEPLOYMENT} -n ${NAMESPACE} -o jsonpath="{.spec.template.spec.containers[?(@.name=='${CONTAINER}')].image}")
echo "Current image: ${CURRENT_IMAGE}"

# Extract current tag
CURRENT_TAG=$(echo ${CURRENT_IMAGE} | cut -d: -f2)
echo "Current tag: ${CURRENT_TAG}"

# Get latest tag from Docker Hub API
# Using wget since curl might not be available in minimal images
LATEST_TAG=$(wget -qO- "https://hub.docker.com/v2/repositories/${IMAGE}/tags?page_size=100" | \
  grep -o '"name":"[^"]*"' | \
  grep "${TAG_PATTERN}" | \
  cut -d'"' -f4 | \
  grep "^${TAG_PATTERN}" | \
  head -1)

if [ -z "${LATEST_TAG}" ]; then
  echo "No tags found matching pattern: ${TAG_PATTERN}"
  exit 0
fi

echo "Latest tag: ${LATEST_TAG}"

# Compare tags
if [ "${CURRENT_TAG}" = "${LATEST_TAG}" ]; then
  echo "Already running latest version"
  exit 0
fi

# Update deployment
NEW_IMAGE="${REGISTRY}/${IMAGE}:${LATEST_TAG}"
echo "Updating deployment to: ${NEW_IMAGE}"

kubectl set image deployment/${DEPLOYMENT} ${CONTAINER}=${NEW_IMAGE} -n ${NAMESPACE}

# Wait for rollout to complete
echo "Waiting for rollout to complete..."
kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s

echo "Update completed successfully!"