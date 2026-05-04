#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "Bootstrapping KIND cluster..."
if ! kind get clusters | grep -q "^ai-observability$"; then
  kind create cluster --config kind/kind-config.yaml --name ai-observability --image kindest/node:v1.25.3
else
  echo "Cluster ai-observability already exists, skipping creation."
fi

if ! docker ps --format '{{.Names}}' | grep -q '^kind-registry$'; then
  echo "Starting local registry..."
  docker run -d --restart=always -p 5001:5000 --name kind-registry registry:2
fi

echo "Connecting registry to kind cluster..."
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5001"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

echo "Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

echo "Waiting for ArgoCD server..."
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=180s

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: argocd-server-nodeport
  namespace: argocd
spec:
  type: NodePort
  selector:
    app.kubernetes.io/name: argocd-server
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30800
EOF

echo "ArgoCD bootstrap complete. Access at http://localhost:30800"

echo "Deploying GitOps apps from repo..."
kubectl apply -f argocd/root-app.yaml

cat <<'EOF'
Next:
  - Access Grafana at http://localhost:30030
  - Access Jenkins at http://localhost:30800
  - Use ArgoCD UI with username 'admin' and password from:
      kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
EOF
