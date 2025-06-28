#!/bin/bash

echo "🔍 Weryfikacja pełnego pipeline CI/CD..."
echo ""

# Kolory
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funkcja do sprawdzania statusu
check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
        return 0
    else
        echo -e "${RED}❌ $2${NC}"
        return 1
    fi
}

# 1. Sprawdź GitHub repository
echo "1️⃣ GitHub Repository:"
if git remote -v | grep -q "parimple/zgdk"; then
    check_status 0 "Repository URL: parimple/zgdk"
else
    check_status 1 "Repository URL nieprawidłowe"
fi

# 2. Sprawdź GitHub Actions
echo ""
echo "2️⃣ GitHub Actions:"
if [ -f ".github/workflows/ci.yml" ]; then
    check_status 0 "Workflow CI/CD istnieje"
    echo "   ⚠️  Pamiętaj o dodaniu DOCKER_PASSWORD w GitHub Secrets!"
else
    check_status 1 "Brak workflow CI/CD"
fi

# 3. Sprawdź Docker Hub
echo ""
echo "3️⃣ Docker Hub:"
IMAGE_REPO=$(grep "repository:" helm/zgdk/values.yaml | head -1 | awk '{print $2}')
if [ "$IMAGE_REPO" = "ppyzel/zgdk" ]; then
    check_status 0 "Image repository: ppyzel/zgdk"
else
    check_status 1 "Nieprawidłowe image repository: $IMAGE_REPO"
fi

# 4. Sprawdź Helm
echo ""
echo "4️⃣ Helm Chart:"
if [ -f "helm/zgdk/Chart.yaml" ]; then
    VERSION=$(grep "^version:" helm/zgdk/Chart.yaml | awk '{print $2}')
    check_status 0 "Helm chart v$VERSION"
    
    # Sprawdź health probes
    if grep -q "livez" helm/zgdk/templates/discord-bot-deployment.yaml 2>/dev/null || grep -q "/health" helm/zgdk/templates/discord-bot-deployment.yaml 2>/dev/null; then
        echo -e "${YELLOW}   ⚠️  Health check endpoints mogą wymagać dostosowania${NC}"
    fi
else
    check_status 1 "Brak Helm chart"
fi

# 5. Sprawdź ArgoCD
echo ""
echo "5️⃣ ArgoCD:"
if [ -f "argocd/zgdk-bot-app.yaml" ] && [ -f "argocd/support-agents-app.yaml" ]; then
    check_status 0 "Manifesty aplikacji istnieją"
    
    # Sprawdź czy aplikacje są zainstalowane w klastrze
    if command -v kubectl &> /dev/null; then
        if kubectl get applications -n argocd &> /dev/null; then
            APPS=$(kubectl get applications -n argocd --no-headers 2>/dev/null | grep -E "(zgdk-bot|support-agents)" | wc -l)
            if [ $APPS -gt 0 ]; then
                check_status 0 "Aplikacje zainstalowane w ArgoCD: $APPS"
            else
                check_status 1 "Aplikacje nie są zainstalowane w ArgoCD"
                echo "   💡 Uruchom: ./scripts/argocd-setup.sh"
            fi
        fi
    else
        echo "   ⚠️  kubectl niedostępny - nie można sprawdzić klastra"
    fi
else
    check_status 1 "Brak manifestów ArgoCD"
fi

# 6. Sprawdź Kubernetes
echo ""
echo "6️⃣ Kubernetes:"
if command -v kubectl &> /dev/null; then
    if kubectl cluster-info &> /dev/null; then
        check_status 0 "Połączono z klastrem"
        
        # Sprawdź namespace
        if kubectl get namespace zgdk &> /dev/null; then
            check_status 0 "Namespace zgdk istnieje"
        else
            check_status 1 "Namespace zgdk nie istnieje"
        fi
    else
        check_status 1 "Nie można połączyć się z klastrem"
    fi
else
    check_status 1 "kubectl nie jest zainstalowany"
fi

# Podsumowanie
echo ""
echo "📊 Podsumowanie Pipeline:"
echo "──────────────────────────"
echo "1. Git push → GitHub"
echo "2. GitHub Actions → Build & Test"
echo "3. Docker Build → Push do ppyzel/zgdk"
echo "4. Update Helm values → Commit"
echo "5. ArgoCD wykrywa zmianę → Sync"
echo "6. Kubernetes → Deploy nowej wersji"
echo ""

# Następne kroki
echo "🚀 Następne kroki:"
echo "1. Zmerguj branch 'fix/repository-urls' do main"
echo "2. Dodaj DOCKER_PASSWORD w GitHub Secrets"
echo "3. Uruchom ./scripts/argocd-setup.sh (jeśli aplikacje nie są zainstalowane)"
echo "4. Push do main uruchomi cały pipeline"
echo ""
echo "🔗 Pomocne linki:"
echo "- GitHub: https://github.com/parimple/zgdk"
echo "- Docker Hub: https://hub.docker.com/r/ppyzel/zgdk"