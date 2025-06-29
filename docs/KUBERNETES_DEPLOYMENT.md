# ZGDK Kubernetes Deployment Guide

## 🚀 Quick Start

### Prerequisites
- ARM64 Linux instance (Ubuntu/Debian)
- At least 4GB RAM
- sudo access

### 1. Install K3s
```bash
./scripts/install-k3s.sh
source ~/.bashrc
```

### 2. Deploy ZGDK
```bash
./scripts/deploy-to-k8s.sh
```

You'll be prompted for:
- Discord Bot Token
- PostgreSQL password
- Gemini API Key (optional)

### 3. Verify Deployment
```bash
kubectl get pods -n zgdk
./scripts/k8s-manage.sh status
```

## 📋 Management

### View Logs
```bash
# Discord bot logs
./scripts/k8s-manage.sh logs

# Specific pod logs
kubectl logs <pod-name> -n zgdk
```

### Update Deployment
```bash
# Update to latest Docker image
./scripts/k8s-manage.sh update

# Manual Helm update
helm upgrade zgdk ./helm/zgdk -n zgdk --reuse-values
```

### Restart Bot
```bash
./scripts/k8s-manage.sh restart
```

### Access Bot Shell
```bash
./scripts/k8s-manage.sh shell
```

## 🔧 Configuration

### Update Config
1. Edit `helm/zgdk/files/config.yml`
2. Update deployment:
   ```bash
   helm upgrade zgdk ./helm/zgdk -n zgdk --reuse-values
   ```

### Update Secrets
```bash
# Discord token
./scripts/k8s-manage.sh secrets

# Database password
kubectl edit secret postgres-secrets -n zgdk
```

## 📊 Monitoring

### Check Pod Status
```bash
kubectl get pods -n zgdk -w
```

### Check Resources
```bash
kubectl top pods -n zgdk
kubectl top nodes
```

### View Events
```bash
kubectl get events -n zgdk --sort-by='.lastTimestamp'
```

## 🐛 Troubleshooting

### Pod CrashLoopBackOff
```bash
# Check logs
kubectl logs <pod-name> -n zgdk --previous

# Describe pod
kubectl describe pod <pod-name> -n zgdk
```

### Database Connection Issues
```bash
# Test connection from bot
kubectl exec -it <bot-pod> -n zgdk -- python -c "import socket; print(socket.connect_ex(('postgres-service', 5432)))"

# Check PostgreSQL
kubectl logs postgres-0 -n zgdk
```

### Discord Connection Issues
```bash
# Check token
kubectl get secret discord-secrets -n zgdk -o yaml

# Verify bot logs
kubectl logs -l app=zgdk,component=discord-bot -n zgdk | grep -E "(ERROR|Connected|Ready)"
```

## 🗑️ Cleanup

### Remove ZGDK
```bash
helm uninstall zgdk -n zgdk
kubectl delete namespace zgdk
```

### Uninstall K3s
```bash
/usr/local/bin/k3s-uninstall.sh
```

## 📁 File Structure
```
zgdk/
├── helm/
│   └── zgdk/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── files/
│       │   └── config.yml
│       └── templates/
│           ├── deployment.yaml
│           ├── discord-bot-deployment.yaml
│           └── ...
├── scripts/
│   ├── install-k3s.sh
│   ├── deploy-to-k8s.sh
│   └── k8s-manage.sh
└── docs/
    └── KUBERNETES_DEPLOYMENT.md
```

## 🔄 CI/CD Integration

The deployment automatically updates when:
1. Code is pushed to main branch
2. GitHub Actions builds new Docker image
3. Helm values are updated with new tag
4. ArgoCD (if configured) syncs the changes

To manually trigger update:
```bash
./scripts/k8s-manage.sh update
```