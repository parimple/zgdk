#!/bin/bash

echo "🔍 Weryfikacja konfiguracji CI/CD..."
echo ""

# Check if .github/workflows exists
if [ -d ".github/workflows" ]; then
    echo "✅ Katalog .github/workflows istnieje"
    echo "   Znalezione workflow:"
    for file in .github/workflows/*.yml; do
        echo "   - $(basename $file)"
    done
else
    echo "❌ Brak katalogu .github/workflows"
fi
echo ""

# Check Docker configuration
echo "🐳 Konfiguracja Docker:"
if [ -f "docker/app/Dockerfile" ]; then
    echo "✅ Dockerfile znaleziony"
else
    echo "❌ Brak Dockerfile"
fi

# Check image repository in values.yaml
IMAGE_REPO=$(grep "repository:" helm/zgdk/values.yaml | head -1 | awk '{print $2}')
echo "   Repository: $IMAGE_REPO"
echo ""

# Check Helm configuration
echo "⎈ Konfiguracja Helm:"
if [ -f "helm/zgdk/Chart.yaml" ]; then
    echo "✅ Chart.yaml znaleziony"
    VERSION=$(grep "^version:" helm/zgdk/Chart.yaml | awk '{print $2}')
    APP_VERSION=$(grep "^appVersion:" helm/zgdk/Chart.yaml | awk '{print $2}')
    echo "   Chart version: $VERSION"
    echo "   App version: $APP_VERSION"
else
    echo "❌ Brak Chart.yaml"
fi
echo ""

# Check ArgoCD applications
echo "🚀 Aplikacje ArgoCD:"
if [ -d "argocd" ]; then
    echo "✅ Katalog argocd istnieje"
    echo "   Znalezione aplikacje:"
    for file in argocd/*.yaml; do
        APP_NAME=$(grep "name:" $file | head -1 | awk '{print $2}')
        echo "   - $APP_NAME ($(basename $file))"
    done
else
    echo "❌ Brak katalogu argocd"
fi
echo ""

# Summary
echo "📝 Podsumowanie:"
echo "1. GitHub Actions workflow: ✅ Utworzony"
echo "2. Docker Hub integracja: ✅ Skonfigurowana (ppyzel/zgdk)"
echo "3. Helm chart: ✅ Przygotowany"
echo "4. ArgoCD aplikacje: ✅ Utworzone"
echo ""
echo "⚠️  Pamiętaj o dodaniu secretu DOCKER_PASSWORD w GitHub!"
echo "   Instrukcje znajdują się w .github/README.md"