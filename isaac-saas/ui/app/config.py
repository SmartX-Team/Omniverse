"""Static configuration: environment, constants, and the tracking annotation schema.

Pure values only - no logic, no I/O. Everything reads its config from here instead of
calling os.environ directly, so there is one obvious place to change behavior.
"""
import os

# --- Kubernetes API (in-cluster) ---
API_BASE = "https://kubernetes.default.svc"
SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"

# --- runtime config (injected via the Deployment env) ---
NAMESPACE = os.environ.get("NAMESPACE", "oos-sim")
IMAGE = os.environ.get("IMAGE", "10.38.38.210/dt-saas/isaac-sim:5.1-exp1")  # image for INSTANCES
NODES = [n for n in os.environ.get("NODES", "l40s,rm352-1,rm352-2").split(",") if n]
PORT = int(os.environ.get("PORT", "8080"))

# GPU products instances are NEVER scheduled onto (permanent hardware constraint,
# e.g. A100 has no NVENC so it cannot serve WebRTC streaming). Distinct from the
# revocable ban system - this can't be cleared from the UI. Case-insensitive
# substring match against the GPU product name.
# ENFORCEMENT (0.15+): with DRA_ENABLED this is enforced PER GPU via the
# per-instance ResourceClaimTemplate's CEL (productName selector), so mixed nodes
# (e.g. sv4000-1 = A6000x2 + A100x1) keep their compatible GPUs schedulable.
# Without DRA it falls back to the legacy node-level exclusion (matches the NODE's
# gpu.product label - which drops mixed nodes entirely; that limitation is why this
# was kept empty during the KCI experiments).
INSTANCE_DENY_PRODUCTS = [p.strip() for p in
                          os.environ.get("INSTANCE_DENY_PRODUCTS", "A100").split(",") if p.strip()]

# --- instance image catalog (registry read API; Create 모달의 이미지/태그 선택) ---
# REGISTRY_KIND  harbor (기본) | dockerhub — registry.py 의 카탈로그 어댑터 선택
# REGISTRY_URL   Harbor API 베이스 (내부 Harbor는 HTTP). dockerhub 면 무시됨.
# REGISTRY_REPOS 선택 가능 레포 목록 (쉼표 구분) — 인스턴스용 이미지만 노출
# REGISTRY_USER/PASS  비공개 프로젝트용 (비우면 익명; 공개 프로젝트면 불필요)
REGISTRY_KIND = os.environ.get("REGISTRY_KIND", "harbor")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://10.38.38.210")
REGISTRY_PROJECT = os.environ.get("REGISTRY_PROJECT", "dt-saas")
REGISTRY_REPOS = [r.strip() for r in
                  os.environ.get("REGISTRY_REPOS", "isaac-sim").split(",") if r.strip()]
REGISTRY_USER = os.environ.get("REGISTRY_USER", "")
REGISTRY_PASS = os.environ.get("REGISTRY_PASS", "")

# --- GPU ban policy store ---
# REDIS_HOST set  -> bans live in Redis (key REDIS_KEY, single JSON blob)
# REDIS_HOST unset -> bans live in a namespace ConfigMap (POLICY_CM) - default
REDIS_HOST = os.environ.get("REDIS_HOST", "")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_KEY = os.environ.get("REDIS_KEY", "isaac-ui:bans")
POLICY_CM = os.environ.get("POLICY_CM", "isaac-ui-policy")

# --- naming of managed objects ---
GROUP = "dt-sim"            # label group on every managed object
PREFIX = "dt-sim-"          # Deployment/Service name prefix per instance

# --- Isaac Sim streaming launch ---
STREAM_CMD = "/isaac-sim/isaac-sim.streaming.sh"
PUBLIC_ADDR_FLAG = "--/app/livestream/publicEndpointAddress="
EXT_SRC_DIR = os.environ.get("EXT_SRC_DIR", "/opt/oos_omniverse_extensions")  # NetAI extensions

# --- code-server (VSCode) sidecar, bundled with each instance ---
# A code-server container ships in the instance pod, sharing WORKSPACE_DIR with the
# Isaac Sim container so researchers can edit the instance's code/config in the browser.
def _flag(v, default):
    return os.environ.get(v, default) not in ("0", "false", "False", "no", "")


CODE_SERVER_ENABLED = _flag("CODE_SERVER_ENABLED", "1")
# Pin and/or mirror to Harbor for reliability (Docker Hub pulls are rate-limited).
CODE_SERVER_IMAGE = os.environ.get("CODE_SERVER_IMAGE", "codercom/code-server:latest")
CODE_SERVER_PORT = int(os.environ.get("CODE_SERVER_PORT", "8443"))            # LB-exposed
CODE_SERVER_CONTAINER_PORT = int(os.environ.get("CODE_SERVER_CONTAINER_PORT", "8080"))
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", EXT_SRC_DIR)  # path opened+edited in VSCode
# Persistence: off -> emptyDir (no StorageClass needed, edits lost on pod restart).
# on  -> a per-instance RWO PVC (edits survive restarts). Needs a (default) StorageClass.
WORKSPACE_PERSIST = _flag("WORKSPACE_PERSIST", "0")
WORKSPACE_STORAGE_CLASS = os.environ.get("WORKSPACE_STORAGE_CLASS", "")       # "" = cluster default
WORKSPACE_SIZE = os.environ.get("WORKSPACE_SIZE", "5Gi")

# --- per-instance metrics (OpenTelemetry Collector sidecar, network-centric) ---
# OTel Collector (hostmetrics:network scraper) exposes a Prometheus endpoint that the
# monitoring-ns Prometheus pulls via pod annotations (no Service port - never on the LB).
# Instance/owner breakdown comes from the app + owner pod labels in PromQL.
METRICS_ENABLED = _flag("METRICS_ENABLED", "1")
# Pin and/or mirror to Harbor (Docker Hub/quay pulls are rate-limited). Origin:
# otel/opentelemetry-collector-contrib:0.119.0  (contrib distro has hostmetrics+prometheus)
METRICS_OTEL_IMAGE = os.environ.get("METRICS_OTEL_IMAGE",
                                    "10.38.38.210/dt-saas/otel-collector-contrib:0.119.0")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9100"))
METRICS_INTERVAL = os.environ.get("METRICS_INTERVAL", "15s")
# Cluster Prometheus the UI dashboard reads from (read-only, in-cluster HTTP). The
# prometheus-community chart's server Service is `prometheus-server` on port 80.
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL",
                                "http://prometheus-server.monitoring.svc.cluster.local")

# --- extended L4 telemetry: node-exporter sidecar (protocol split + TCP retransmits) ---
# hostmetrics:network gives interface x direction BYTES only. A loopback node-exporter
# (netstat/sockstat/tcpstat collectors) adds TCP retransmits, TCP-segment vs UDP-datagram
# protocol counts, and socket/connection counts - the per-protocol signal hostmetrics
# lacks. It binds 127.0.0.1 (never exposed); the OTel collector scrapes it and re-exports
# on METRICS_PORT (single scrape port). Requires METRICS_ENABLED (OTel does the merge).
# NOTE: per-PORT bytes and TCP RTT/jitter still need Cilium Hubble / eBPF (cluster-level).
NETSTAT_ENABLED = _flag("NETSTAT_ENABLED", "1")
NETSTAT_IMAGE = os.environ.get("NETSTAT_IMAGE", "10.38.38.210/dt-saas/node-exporter:1.8")
NETSTAT_PORT = int(os.environ.get("NETSTAT_PORT", "9101"))  # loopback only, scraped by OTel

# --- GPU allocation via Dynamic Resource Allocation (DRA) ---
# On  -> each instance requests its GPU through a per-instance ResourceClaimTemplate
#        (DRA_DEVICE_CLASS) carrying a CEL deny-list. THIS is what makes per-UUID GPU
#        bans actually enforced at schedule time instead of best-effort display. Needs
#        the NVIDIA DRA driver (k8s-dra-driver-gpu) and Kubernetes >= 1.34 (DRA GA).
# Off -> legacy device-plugin request (nvidia.com/gpu: 1); UUID bans stay display-only.
DRA_ENABLED = _flag("DRA_ENABLED", "1")
DRA_API_VERSION = os.environ.get("DRA_API_VERSION", "resource.k8s.io/v1")  # GA in 1.34
DRA_DRIVER = os.environ.get("DRA_DRIVER", "gpu.nvidia.com")        # device.driver + attr domain
DRA_DEVICE_CLASS = os.environ.get("DRA_DEVICE_CLASS", "gpu.nvidia.com")    # DeviceClass name

# --- GPU ban display: count UUID-banned GPUs as "used" (grey) instead of a distinct
# "banned" marker. On  -> a banned GPU is folded into the occupied/used slots and greyed
#                         out (this DISGUISE was used during the KCI review period).
# Off (default, post-KCI) -> bans are shown honestly as ban pips. Free accounting:
# under DRA every UUID ban is schedule-time enforced, so ALL bans reduce free
# regardless of this flag or the legacy 'applied' marker (see gpu.py).
GPU_BAN_AS_USED = _flag("GPU_BAN_AS_USED", "0")

# GPUs that are permanently unusable (hardware fault / reserved) and must be banned from
# the first UI load. Seeded into the ban store at startup (shows as a normal gpu ban and,
# with GPU_BAN_AS_USED, greys out + drops launchable). Format: "node:UUID" items, comma
# or space separated. Re-ensured on every startup (a UI remove is undone on restart).
DEFAULT_GPU_BANS = os.environ.get("DEFAULT_GPU_BANS", "")

# --- scene load history (which USD stage stressed which GPU, see scenes.py) ---
# Instances (6.0+ image with /opt/experiment/stage_report.py) POST stage open/close
# events to SCENE_REPORT_URL; the UI stores sessions in the SCENES_CM ConfigMap and
# joins them with DCGM stats so heavy scenes per GPU model become visible/queryable.
SCENE_REPORT_ENABLED = _flag("SCENE_REPORT_ENABLED", "1")
SCENE_REPORT_URL = os.environ.get(
    "SCENE_REPORT_URL", f"http://isaac-ui.{NAMESPACE}.svc/api/stage-report")
SCENES_CM = os.environ.get("SCENES_CM", "isaac-ui-scenes")
SCENES_MAX = int(os.environ.get("SCENES_MAX", "500"))      # keep newest N sessions

# --- tracking metadata schema (see tracking.py) ---
# Keys are stable so a future DB-backed store can mirror the exact same fields.
ANN_PREFIX = "dt-saas.wks/"
ANN_OWNER = ANN_PREFIX + "owner"            # who requested the instance
ANN_DESC = ANN_PREFIX + "description"       # free-text purpose / implementation note
ANN_CREATEDB = ANN_PREFIX + "created-by"    # source of creation (ui / cli / manifest)
ANN_TRACKING = ANN_PREFIX + "tracking"      # JSON blob, reserved for detailed tracking
ANN_CODE_PW = ANN_PREFIX + "code-server-pw"  # per-instance code-server password (lab posture)
