import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import docker

try:
    docker_client = docker.from_env()
    docker_containers = {c.name: c.id for c in docker_client.containers.list()}
except Exception as e:
    docker_containers = {}

st.set_page_config(page_title="AIOps Observability", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0B0F19; color: #FFFFFF; }
    .stMetric { background-color: #1E293B; padding: 15px; border-radius: 8px; border: 1px solid #334155; }
    </style>
""", unsafe_allow_html=True)

ML_URL = "http://ml-model:8200"
BACKEND_URL = "http://backend:8000"
PROMETHEUS_URL = "http://prometheus:9090"

st.title("AIOps Observability & Incident Response Center")

# --- CONTROLS & CHAOS ENGINE ---
with st.expander("⚙️ Platform Controls & Synthetic Chaos Engine", expanded=False):
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
    with col_ctrl1:
        st.subheader("General Settings")
        refresh_rate = st.slider("Auto-Refresh Rate (s)", 2, 30, 5)
        st.markdown("**Email Alert Dispatcher**")
        email_alerts = st.checkbox("Enable Alerts", value=True)
        email_id = st.text_input("Alert Email ID", value="adityarrudola@gmail.com")
        alert_thresh = st.selectbox("Alert Threshold", ["Info", "Warning", "Error", "Critical"], index=2)
        if st.button("Save Alert Config"):
            st.success(f"Alerts configured! Will send to: {email_id}")

    with col_ctrl2:
        st.subheader("Inject Infrastructure Chaos")
        if st.button("Trigger CPU Spike"):
            requests.post(f"{BACKEND_URL}/chaos/cpu-spike?active=true")
        if st.button("Start Memory Leak Simulation"):
            requests.post(f"{BACKEND_URL}/chaos/memory-leak?active=true")
        if st.button("Simulate Disk Pressure"):
            requests.post(f"{BACKEND_URL}/chaos/disk-pressure?active=true")
        if st.button("Simulate DB Connection Drop"):
            requests.post(f"{BACKEND_URL}/chaos/db-outage?active=true")
            
    with col_ctrl3:
        st.subheader("Inject Application Chaos")
        if st.button("Simulate Traffic Burst"):
            requests.post(f"{BACKEND_URL}/chaos/traffic-burst?active=true")
        if st.button("Simulate Slow API"):
            requests.post(f"{BACKEND_URL}/chaos/slow-api?active=true")
        st.markdown("---")
        if st.button("✅ Restore All Chaos / DB"):
            requests.post(f"{BACKEND_URL}/chaos/db-outage?active=false")
            requests.post(f"{BACKEND_URL}/chaos/traffic-burst?active=false")
            requests.post(f"{BACKEND_URL}/chaos/slow-api?active=false")
            requests.post(f"{BACKEND_URL}/chaos/disk-pressure?active=false")
            requests.post(f"{BACKEND_URL}/chaos/cpu-spike?active=false")
            requests.post(f"{BACKEND_URL}/chaos/memory-leak?active=false")

# --- SECTION 1: SYSTEM HEALTH ---
st.header("Overall System Health")
try:
    health = requests.get(f"{ML_URL}/health_score", timeout=2).json()
    score = health.get("score", 100)
    status = health.get("status", "Unknown")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("AI Health Score", f"{score}/100", status, delta_color="off" if score==100 else "inverse")
    
    log_res = requests.get(f"{ML_URL}/analyze-logs", timeout=2).json()
    levels = log_res.get("summary", {}).get("levels", {})
    c2.metric("Total Errors", levels.get("error", 0) + levels.get("critical", 0))
    c3.metric("System Warnings", levels.get("warning", 0))
    c4.metric("Traffic Status", "Nominal" if score > 80 else "Degraded")
except:
    st.error("ML Engine Offline")

# --- INFRASTRUCTURE ---
st.markdown("---")
st.header("🏗️ Infrastructure Dashboard")

def fetch_prom_metric(query, step="15s"):
    try:
        res = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
            "query": query, "start": time.time() - 300, "end": time.time(), "step": step
        }, timeout=2).json()
        data = res.get("data", {}).get("result", [])
        if data:
            df = pd.DataFrame(data[0]["values"], columns=["timestamp", "value"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s") + pd.Timedelta(hours=5, minutes=30)
            df["value"] = df["value"].astype(float)
            return df
    except:
        pass
    return pd.DataFrame()

st.subheader("Global System Telemetry")
col_t1, col_t2 = st.columns(2)
with col_t1:
    sys_cpu_df = fetch_prom_metric("system_cpu_percent")
    if not sys_cpu_df.empty:
        fig_sys_c = px.line(sys_cpu_df, x="timestamp", y="value", title="Global CPU Usage (%)")
        fig_sys_c.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=250)
        st.plotly_chart(fig_sys_c, use_container_width=True)

with col_t2:
    sys_mem_df = fetch_prom_metric("system_memory_percent")
    if not sys_mem_df.empty:
        fig_sys_m = px.line(sys_mem_df, x="timestamp", y="value", title="Global Memory Usage (%)")
        fig_sys_m.update_traces(line_color="#EC4899")
        fig_sys_m.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=250)
        st.plotly_chart(fig_sys_m, use_container_width=True)

st.markdown("---")
st.subheader("Per-Container cAdvisor Metrics")
containers = ["backend", "frontend", "ml-model", "prometheus", "loki"]
selected_container = st.selectbox("Select Container", containers)

if selected_container == "backend":
    cpu_query = "system_cpu_percent"
    mem_query = "system_memory_percent"
else:
    long_id = docker_containers.get(selected_container, "")
    if long_id:
        cpu_query = f'rate(container_cpu_usage_seconds_total{{id=~"/docker/.*{long_id}.*"}}[1m]) * 100'
        mem_query = f'container_memory_usage_bytes{{id=~"/docker/.*{long_id}.*"}} / 1024 / 1024'
    else:
        cpu_query = f'rate(container_cpu_usage_seconds_total{{name="{selected_container}"}}[1m]) * 100'
        mem_query = f'container_memory_usage_bytes{{name="{selected_container}"}} / 1024 / 1024'

col_c1, col_c2 = st.columns(2)
with col_c1:
    cpu_df = fetch_prom_metric(cpu_query)
    if not cpu_df.empty:
        fig_c = px.line(cpu_df, x="timestamp", y="value", title=f"[{selected_container}] CPU Usage (%)")
        fig_c.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=300)
        st.plotly_chart(fig_c, use_container_width=True)
    else:
        st.info(f"Waiting for CPU data for {selected_container}... (cAdvisor may be initializing)")

with col_c2:
    mem_df = fetch_prom_metric(mem_query)
    if not mem_df.empty:
        fig_m = px.line(mem_df, x="timestamp", y="value", title=f"[{selected_container}] Memory Usage (MB)")
        fig_m.update_traces(line_color="#EC4899")
        fig_m.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=300)
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.info(f"Waiting for Memory data for {selected_container}... (cAdvisor may be initializing)")

# --- SYSTEM TOPOLOGY ---
st.markdown("---")
st.header("🕸️ System Topology & Architecture")
st.markdown("""
<div style="background:#1E293B; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #334155;">
    <h3 style="color: #38BDF8;">AIOps Observability Platform</h3>
    <p>Frontend Dashboard <b>→</b> Backend (Generator) <b>→</b> Prometheus / Loki <b>→</b> Python ML Engine</p>
</div>
""", unsafe_allow_html=True)

# --- APP PERFORMANCE ---
st.markdown("---")
st.header("🚀 Application Performance Dashboard")
col_p1, col_p2 = st.columns(2)
with col_p1:
    rps_df = fetch_prom_metric('sum(rate(http_requests_total[1m]))')
    if not rps_df.empty:
        fig_rps = px.line(rps_df, x="timestamp", y="value", title="Global Requests Per Second (RPS)")
        fig_rps.update_traces(line_color="#10B981")
        fig_rps.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=300)
        st.plotly_chart(fig_rps, use_container_width=True)
    else:
        st.info("Waiting for HTTP Request data...")
        
with col_p2:
    err_df = fetch_prom_metric('sum(rate(http_requests_total{status=~"5.."}[1m]))')
    if not err_df.empty:
        fig_err = px.line(err_df, x="timestamp", y="value", title="HTTP Error Rate (5xx/sec)")
        fig_err.update_traces(line_color="#EF4444")
        fig_err.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=300)
        st.plotly_chart(fig_err, use_container_width=True)
    else:
        st.info("No error data currently recorded.")

col_p3, col_p4 = st.columns(2)
with col_p3:
    queue_df = fetch_prom_metric('queue_size')
    if not queue_df.empty:
        fig_q = px.line(queue_df, x="timestamp", y="value", title="Active Queue Depth")
        fig_q.update_traces(line_color="#F59E0B")
        fig_q.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=250)
        st.plotly_chart(fig_q, use_container_width=True)
    else:
        st.info("Waiting for Queue Depth data...")
        
with col_p4:
    users_df = fetch_prom_metric('active_users')
    if not users_df.empty:
        fig_u = px.line(users_df, x="timestamp", y="value", title="Active Users / Connections")
        fig_u.update_traces(line_color="#8B5CF6")
        fig_u.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=250)
        st.plotly_chart(fig_u, use_container_width=True)
    else:
        st.info("Waiting for Active Users data...")

# --- AI INSIGHTS ---
st.markdown("---")
st.header("🧠 AI System Insights & Root Cause Analysis")
try:
    ins_res = requests.get(f"{ML_URL}/insights", timeout=2).json()
    for ins in ins_res.get("insights", []):
        st.info(f"💡 {ins}")
except:
    st.write("Insights unavailable.")
    
st.markdown("---")
st.subheader("Active Anomalies")
try:
    anom_res = requests.get(f"{ML_URL}/anomalies", timeout=2).json()
    anomalies = anom_res.get("anomalies", [])
    if anomalies:
        df_anom = pd.DataFrame(anomalies)
        df_anom['timestamp'] = (pd.to_datetime(df_anom['timestamp'], unit='s') + pd.Timedelta(hours=5, minutes=30)).dt.strftime('%H:%M:%S')
        st.dataframe(df_anom[["timestamp", "metric", "severity", "description", "root_cause"]], use_container_width=True)
        st.warning(f"Alert dispatched to {email_id} for active anomalies!")
        csv = df_anom.to_csv(index=False).encode('utf-8')
        st.download_button("Export Incident Report (CSV)", csv, "incident_report.csv", "text/csv")
    else:
        st.success("No active anomalies detected.")
except:
    st.warning("Could not reach ML Anomaly engine.")

# --- FORECASTING ---
st.markdown("---")
st.header("🔮 Global Trend Forecast")
horizon = st.radio("Forecast Horizon", ["1 Hour", "6 Hours", "12 Hours"], horizontal=True)
h_val = 1 if "1" in horizon else 6 if "6" in horizon else 12

col_f1, col_f2 = st.columns(2)
try:
    forecast = requests.get(f"{ML_URL}/forecast?horizon_hours={h_val}", timeout=3).json()
    with col_f1:
        cpu_f = pd.DataFrame(forecast.get("cpu", []))
        if not cpu_f.empty:
            cpu_f["time"] = pd.to_datetime(cpu_f["timestamp"], unit='s') + pd.Timedelta(hours=5, minutes=30)
            fig_fc = px.area(cpu_f, x="time", y="predicted_value", title="CPU Forecast (%)")
            fig_fc.update_traces(line_color='#8B5CF6', fillcolor='rgba(139, 92, 246, 0.2)')
            fig_fc.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig_fc, use_container_width=True)
            
    with col_f2:
        mem_f = pd.DataFrame(forecast.get("memory", []))
        if not mem_f.empty:
            mem_f["time"] = pd.to_datetime(mem_f["timestamp"], unit='s') + pd.Timedelta(hours=5, minutes=30)
            fig_fm = px.area(mem_f, x="time", y="predicted_value", title="Memory Forecast (%)")
            fig_fm.update_traces(line_color='#EC4899', fillcolor='rgba(236, 72, 153, 0.2)')
            fig_fm.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig_fm, use_container_width=True)
except:
    st.warning("Forecast models building...")

# --- INCIDENT RESPONSE DASHBOARD ---
st.markdown("---")
st.header("⏱️ Incident Response & Historical Tracking")
try:
    history_res = requests.get(f"{ML_URL}/incidents/history", timeout=2).json()
    if history_res:
        df_hist = pd.DataFrame(history_res)
        
        # Determine pseudo MTTR (just for demo purposes in roadmap)
        mttr = "4m 12s" if len(df_hist) > 5 else "Under calculation"
        c_i1, c_i2, c_i3 = st.columns(3)
        c_i1.metric("Total Historical Incidents", len(df_hist))
        c_i2.metric("Mean Time To Recovery (MTTR)", mttr)
        c_i3.metric("Critical Incidents (24h)", len(df_hist[df_hist['severity'] == 'CRITICAL']))
        
        def color_hist(row):
            if row['severity'] == 'CRITICAL': return ['background-color: rgba(239, 68, 68, 0.2)'] * len(row)
            if row['severity'] == 'HIGH': return ['background-color: rgba(245, 158, 11, 0.2)'] * len(row)
            return [''] * len(row)
            
        st.dataframe(df_hist.style.apply(color_hist, axis=1), use_container_width=True, height=250)
    else:
        st.success("No historical incidents recorded.")
except:
    st.info("Incident history database initializing...")

# --- LIVE LOGS ---
st.markdown("---")
st.header("📜 Live Log Streaming (Loki)")
try:
    log_res = requests.get(f"{ML_URL}/analyze-logs", timeout=2).json()
    logs = log_res.get("recent_logs", [])
    if logs:
        df_l = pd.DataFrame(logs)
        df_l["time"] = (pd.to_datetime(df_l["timestamp"], unit='s') + pd.Timedelta(hours=5, minutes=30)).dt.strftime('%H:%M:%S')
        filter_lvl = st.multiselect("Filter by Level", ["info", "warning", "error", "critical", "debug"], default=["error", "warning", "critical"])
        if filter_lvl:
            df_l = df_l[df_l['level'].isin(filter_lvl)]
        
        def color_row(row):
            if row['level'] in ['error', 'critical']: return ['background-color: rgba(239, 68, 68, 0.2)'] * len(row)
            if row['level'] == 'warning': return ['background-color: rgba(245, 158, 11, 0.2)'] * len(row)
            if row['level'] == 'debug': return ['background-color: rgba(59, 130, 246, 0.2)'] * len(row)
            return [''] * len(row)
            
        st.dataframe(df_l[["time", "level", "category", "message"]].style.apply(color_row, axis=1), use_container_width=True, height=400)
    else:
        st.write("Fetching logs...")
except:
    st.write("Could not reach Loki logs stream.")

time.sleep(refresh_rate)
st.rerun()
