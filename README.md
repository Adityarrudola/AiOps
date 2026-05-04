# Ai-Observability Monorepo

This repository has been refactored into a local-first, GitOps-driven DevOps + AIOps demo platform.

## Architecture

- `apps/backend` — FastAPI AI observability backend with Prometheus metrics and JSON logging.
- `apps/frontend` — Simple demo UI for system status and alert surface.
- `apps/aiops` — Python anomaly detection service consuming Prometheus metrics and producing alerts.
- `apps/load-generator` — Traffic generator for backend workloads.
- `charts/*` — Helm charts for each application.
- `argocd/*` — App-of-Apps GitOps manifests for ArgoCD.
- `jenkins/*` — Jenkins pipeline and helper script to build images and update Helm values.
- `infra/azure` — Optional Terraform cloud readiness layer for AKS + ACR.
- `kind/kind-config.yaml` — Local KIND cluster configuration.
- `scripts/bootstrap-kind.sh` — Bootstrap script for local cluster and ArgoCD.

## Local-first flow

1. Developer commits to Git.
2. Jenkins pipeline builds Docker images and tags them.
3. Jenkins updates Helm `values.yaml` with image tags.
4. ArgoCD detects Git changes and syncs deployments.
5. Kubernetes services run on KIND.
6. Prometheus metrics and Grafana dashboards are available.
7. AIOps service detects anomalies and emits alerts.

## Run locally

```bash
cd /Users/adityarudola/Desktop/Ai-Observability
bash scripts/bootstrap-kind.sh
```

Then open:

- Backend: `http://backend.default.svc.cluster.local:8000` (inside cluster)
- Frontend: `http://frontend.default.svc.cluster.local:3000`
- Grafana: http://localhost:30030
- Jenkins: http://localhost:30800

## Notes

- The `infra/azure` folder is optional demo IaC and does not run in the local KIND flow.
- All deployment changes are intended to be driven by Git via ArgoCD.
