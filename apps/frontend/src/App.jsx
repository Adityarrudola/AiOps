export default function App() {
  return (
    <div className="page">
      <header>
        <h1>AI Observability Demo</h1>
        <p>GitOps → Jenkins → ArgoCD → Kubernetes → Metrics → AIOps</p>
      </header>

      <section>
        <h2>Architecture</h2>
        <p>This frontend is part of the demo stack, deployed through ArgoCD from Git commits.</p>
      </section>

      <section>
        <h2>Demo flow</h2>
        <ul>
          <li>Commit code and push to Git</li>
          <li>Jenkins builds images and updates Helm values</li>
          <li>ArgoCD syncs the new deployment</li>
          <li>Prometheus scrapes Kubernetes metrics</li>
          <li>AIOps service detects anomalies and emits alerts</li>
        </ul>
      </section>

      <section>
        <h2>Links</h2>
        <ul>
          <li><a href="http://localhost:30030" target="_blank">Grafana</a></li>
          <li><a href="http://localhost:30800" target="_blank">Jenkins</a></li>
        </ul>
      </section>
    </div>
  )
}
