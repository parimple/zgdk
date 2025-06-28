#!/bin/bash

echo "🚀 Instalacja aplikacji ZGDK w ArgoCD..."
echo ""

# Sprawdź czy kubectl jest dostępny
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl nie jest zainstalowany"
    exit 1
fi

# Sprawdź czy ArgoCD jest zainstalowany
if ! kubectl get namespace argocd &> /dev/null; then
    echo "❌ Namespace 'argocd' nie istnieje. Zainstaluj ArgoCD najpierw."
    exit 1
fi

# Sprawdź czy możemy połączyć się z klastrem
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Nie można połączyć się z klastrem Kubernetes"
    exit 1
fi

echo "✅ Połączono z klastrem Kubernetes"
echo ""

# Utwórz namespace zgdk jeśli nie istnieje
echo "📦 Tworzenie namespace zgdk..."
kubectl create namespace zgdk --dry-run=client -o yaml | kubectl apply -f -

# Zainstaluj aplikację głównego bota
echo "🤖 Instalacja aplikacji zgdk-bot..."
kubectl apply -f argocd/zgdk-bot-app.yaml

# Zainstaluj aplikację support agents
echo "🤝 Instalacja aplikacji support-agents..."
kubectl apply -f argocd/support-agents-app.yaml

echo ""
echo "⏳ Oczekiwanie na synchronizację aplikacji..."
sleep 5

# Sprawdź status aplikacji
echo ""
echo "📊 Status aplikacji:"
kubectl get applications -n argocd | grep -E "(NAME|zgdk-bot|support-agents)"

echo ""
echo "🔍 Szczegóły synchronizacji:"
kubectl get applications zgdk-bot -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null && echo " - zgdk-bot"
kubectl get applications support-agents -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null && echo " - support-agents"

echo ""
echo "✅ Aplikacje zostały zainstalowane w ArgoCD!"
echo ""
echo "🎯 Następne kroki:"
echo "1. Sprawdź UI ArgoCD: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "2. Otwórz: https://localhost:8080"
echo "3. Login: admin / hasło z: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo ""
echo "📝 Polecenia pomocnicze:"
echo "- Status: kubectl get applications -n argocd"
echo "- Sync ręczny: kubectl patch application zgdk-bot -n argocd --type merge -p '{\"operation\":{\"sync\":{\"revision\":\"main\"}}}'"
echo "- Logi: kubectl logs -n zgdk -l app=zgdk -f"