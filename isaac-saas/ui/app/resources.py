"""Pure builders for Kubernetes object specs + small response-parsing helpers.

No I/O: given inputs, return dicts/strings. Trivial to unit-test and to restructure
(e.g. split into a template file or Helm chart) without touching the services.
"""
import datetime
import re

from . import config
from .tracking import build_annotations


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _label_safe(v):
    """Sanitize a value into a valid RFC1123 label (used for the Prometheus owner label):
    lowercase, [a-z0-9-], must start/end alphanumeric, <=63 chars."""
    s = re.sub(r"[^a-z0-9-]", "-", (v or "").lower()).strip("-")[:63].strip("-")
    return s or "unknown"


def _otel_config(port, interval, netstat_target=None):
    """OpenTelemetry Collector config: hostmetrics(network) -> prometheus endpoint.
    network stats are netns-scoped, so in the shared pod netns this reports the instance's
    interfaces (no host mount). Self-telemetry disabled; only :PORT/metrics is served.

    If netstat_target ("host:port") is given, ALSO scrape a loopback node-exporter and
    merge its series (TCP retransmits, TCP/UDP protocol counts, sockets) into the same
    /metrics export - so a single scrape port carries both signal sets."""
    recv = ["hostmetrics"]
    extra = ""
    if netstat_target:
        recv.append("prometheus")
        extra = (
            "  prometheus:\n"
            "    config:\n"
            "      scrape_configs:\n"
            "        - job_name: netexporter\n"
            f"          scrape_interval: {interval}\n"
            "          static_configs:\n"
            f'            - targets: ["{netstat_target}"]\n')
    return (
        "receivers:\n"
        "  hostmetrics:\n"
        f"    collection_interval: {interval}\n"
        "    scrapers:\n"
        "      network:\n"
        + extra +
        "exporters:\n"
        "  prometheus:\n"
        f"    endpoint: 0.0.0.0:{port}\n"
        "service:\n"
        "  telemetry:\n"
        "    metrics:\n"
        "      level: none\n"
        "  pipelines:\n"
        "    metrics:\n"
        f"      receivers: [{', '.join(recv)}]\n"
        "      exporters: [prometheus]\n"
    )


def _cel_safe(token):
    """Sanitize an env-sourced product token for embedding in a CEL regex string:
    keep alphanumerics, space, dot, dash, underscore. Products are names like
    "A100" / "RTX A6000", so this never changes a legitimate value."""
    return re.sub(r"[^A-Za-z0-9 ._-]", "", token or "")


def _cel_gpu_exclude(uuids=None, products=None, driver=None):
    """CEL selector: any device of `driver` that is NOT UUID-banned and NOT of a
    denied product family. Product match mirrors policy.product_denied(): case-
    insensitive substring, via RE2 `(?i)` in CEL string.matches(). The productName
    attribute is the same one instances._find_product() reads off ResourceSlices."""
    driver = driver or config.DRA_DRIVER
    parts = [f'device.driver == "{driver}"']
    if uuids:
        lst = ", ".join(f'"{u}"' for u in uuids)
        parts.append(f'!(device.attributes["{driver}"].uuid in [{lst}])')
    for p in (products or []):
        p = _cel_safe(p)
        if p:
            parts.append(
                f'!device.attributes["{driver}"].productName.matches("(?i){p}")')
    return " && ".join(parts)


def resource_claim_template(name, banned_uuids=None, denied_products=None):
    """Per-instance ResourceClaimTemplate: exactly one GPU from the DRA device class,
    excluding banned UUIDs and denied product families via CEL (per-GPU enforcement -
    mixed nodes keep their compatible GPUs). resource.k8s.io/v1 (GA) `exactly` shape.
    The generated ResourceClaim is owned by the pod (GC'd on pod delete); the instance
    service creates/deletes the template itself."""
    app = config.PREFIX + name
    expr = _cel_gpu_exclude(banned_uuids or [], denied_products or [])
    return {
        "apiVersion": config.DRA_API_VERSION, "kind": "ResourceClaimTemplate",
        "metadata": {"name": f"{app}-gpu", "namespace": config.NAMESPACE,
                     "labels": {"app": app, "group": config.GROUP}},
        "spec": {"spec": {"devices": {"requests": [{
            "name": "gpu",
            "exactly": {"deviceClassName": config.DRA_DEVICE_CLASS,
                        "allocationMode": "ExactCount", "count": 1,
                        "selectors": [{"cel": {"expression": expr}}]}}]}}}}


def deployment(name, ip=None, owner="", desc="", nodes=None, code_pw="", image=None,
               stage=None, camera=None):
    """Build the Deployment spec for one Isaac Sim streaming instance.

    nodes:   hostnames eligible for this instance (ban policy already applied by the
             caller). Defaults to config.NODES.
    code_pw: if code-server is enabled, the per-instance VSCode password (set as the
             code-server container's PASSWORD env and recorded as an annotation so the
             UI can show it). Ignored when CODE_SERVER_ENABLED is off.
    image:   instance container image. Defaults to config.IMAGE. The caller (web
             layer) MUST have validated it against the registry catalog already.
    stage:   USD stage URL to auto-open at launch (STARTUP_USD_STAGE). Falls back to
             config.DEFAULT_STAGE. camera: optional camera prim path to activate."""
    app = config.PREFIX + name
    nodes = nodes or config.NODES
    image = image or config.IMAGE
    # per-instance stage override, else the cluster-wide default; strip stray whitespace
    stage = (stage or config.DEFAULT_STAGE or "").strip()
    camera = (camera or config.DEFAULT_CAMERA or "").strip()
    args = [config.STREAM_CMD]
    if ip:
        args.append(config.PUBLIC_ADDR_FLAG + ip)

    annotations = build_annotations(owner, desc, created_at=_now_iso(), stage=stage)

    isaac = {
        "name": "isaac-sim", "image": image, "imagePullPolicy": "IfNotPresent",
        "args": args,
        "env": [
            {"name": "ACCEPT_EULA", "value": "Y"},
            {"name": "PRIVACY_CONSENT", "value": "Y"},
            {"name": "OMNI_KIT_ALLOW_ROOT", "value": "1"},
            {"name": "OMNI_SERVER", "value": "omniverse://10.38.38.32/"},
            {"name": "OMNI_USER", "value": "admin"},
            {"name": "OMNI_PASS", "valueFrom": {"secretKeyRef": {"name": "nucleus-cred", "key": "OMNI_PASS"}}},
            {"name": "EXT_PREFIX", "value": "[NetAI]"},
            {"name": "EXT_SRC_DIR", "value": config.EXT_SRC_DIR},
            {"name": "NVIDIA_DRIVER_CAPABILITIES", "value": "all"}],
        "resources": {"limits": {"nvidia.com/gpu": 1}},
        "volumeMounts": [{"name": "dshm", "mountPath": "/dev/shm"}]}

    # startup stage auto-open: the 6.0+ image entrypoint turns STARTUP_USD_STAGE into a
    # kit `--exec open_stage_with_camera.py <url> [camera]`. Older images ignore the env,
    # so injecting it only when a stage is set stays backward-compatible.
    if stage:
        isaac["env"].append({"name": "STARTUP_USD_STAGE", "value": stage})
        if camera:
            isaac["env"].append({"name": "STARTUP_CAMERA_PATH", "value": camera})

    # scene load history: the 6.0+ image's entrypoint starts a stage-event reporter
    # (--exec /opt/experiment/stage_report.py) when REPORT_URL is set. Older images
    # simply ignore these env vars, so it is safe to inject them unconditionally.
    if config.SCENE_REPORT_ENABLED:
        isaac["env"] += [{"name": "REPORT_URL", "value": config.SCENE_REPORT_URL},
                         {"name": "INSTANCE_NAME", "value": name}]

    containers = [isaac]                 # isaac-sim MUST stay index 0 (reconcile patches it)
    # DRA: request the GPU via the per-instance ResourceClaim (drop the device-plugin
    # limit set in the isaac literal above), so per-UUID bans in the claim's CEL bite.
    if config.DRA_ENABLED:
        isaac["resources"] = {"claims": [{"name": "gpu"}]}
    init_containers = []
    volumes = [{"name": "dshm", "emptyDir": {"medium": "Memory", "sizeLimit": "8Gi"}}]
    pod_labels = {"app": app, "group": config.GROUP}
    pod_annotations = {}

    if config.CODE_SERVER_ENABLED:
        annotations[config.ANN_CODE_PW] = code_pw
        ws = config.WORKSPACE_DIR
        ws_mount = {"name": "workspace", "mountPath": ws}
        # shared, editable workspace - emptyDir (ephemeral) or a per-instance RWO PVC
        if config.WORKSPACE_PERSIST:
            volumes.append({"name": "workspace",
                            "persistentVolumeClaim": {"claimName": f"{app}-workspace"}})
        else:
            volumes.append({"name": "workspace", "emptyDir": {}})
        # seed the workspace from the image's source dir ONCE; -n keeps later edits
        # (matters on a PVC; an emptyDir is fresh each pod so it always gets a full copy)
        init_containers.append({
            "name": "seed-workspace", "image": image, "imagePullPolicy": "IfNotPresent",
            "command": ["sh", "-c", f"cp -an {ws}/. /seed/ 2>/dev/null || true"],
            "volumeMounts": [{"name": "workspace", "mountPath": "/seed"}]})
        # isaac reads its extensions from the (now shared) dir, so edits reach the sim
        isaac["volumeMounts"].append(ws_mount)
        containers.append({
            "name": "code-server", "image": config.CODE_SERVER_IMAGE, "imagePullPolicy": "IfNotPresent",
            "args": ["--bind-addr", f"0.0.0.0:{config.CODE_SERVER_CONTAINER_PORT}",
                     "--disable-telemetry", "--disable-update-check", ws],
            "env": [{"name": "PASSWORD", "value": code_pw}],
            "ports": [{"name": "code-server", "containerPort": config.CODE_SERVER_CONTAINER_PORT}],
            "resources": {"requests": {"cpu": "100m", "memory": "256Mi"},
                          "limits": {"cpu": "1", "memory": "1Gi"}},
            "volumeMounts": [ws_mount]})

    if config.METRICS_ENABLED:
        # OpenTelemetry Collector as a NATIVE SIDECAR (init container, restartPolicy:Always).
        # Native sidecars can crash/restart "without affecting the main application
        # container", and with no readinessProbe they do NOT gate Pod readiness - so a
        # broken collector never deregisters the instance from its LoadBalancer. It shares
        # the pod netns, so the hostmetrics:network scraper sees the instance's real traffic
        # (no host mount). Exposes a Prometheus endpoint on :METRICS_PORT that monitoring-ns
        # Prometheus pulls via the annotations below; the port is NOT on the Service.
        # NOTE: a native sidecar starts before isaac, so the image must be reachable
        # (mirror to Harbor); if it can't be pulled, set METRICS_ENABLED=0.
        pod_labels["owner"] = _label_safe(owner)        # enables `sum by (owner)` in PromQL
        pod_annotations.update({"prometheus.io/scrape": "true",
                                "prometheus.io/port": str(config.METRICS_PORT),
                                "prometheus.io/path": "/metrics"})
        # Extended L4 telemetry: a loopback node-exporter (netdev/netstat/sockstat/tcpstat)
        # adds TCP retransmits, TCP-segment vs UDP-datagram protocol counts, and socket/
        # connection counts - the per-protocol signal hostmetrics:network lacks. Bound to
        # 127.0.0.1 (never exposed on the pod IP or Service); the otel collector scrapes it
        # and re-exports on METRICS_PORT, so Prometheus still hits one port.
        netstat_target = None
        if config.NETSTAT_ENABLED:
            netstat_target = f"127.0.0.1:{config.NETSTAT_PORT}"
            init_containers.append({
                "name": "net-exporter", "image": config.NETSTAT_IMAGE,
                "imagePullPolicy": "IfNotPresent",
                "restartPolicy": "Always",              # native sidecar
                "args": [f"--web.listen-address=127.0.0.1:{config.NETSTAT_PORT}",
                         "--collector.disable-defaults", "--collector.netdev",
                         "--collector.netstat", "--collector.sockstat",
                         "--collector.tcpstat"],
                "resources": {"requests": {"cpu": "20m", "memory": "32Mi"},
                              "limits": {"cpu": "100m", "memory": "64Mi"}},
                "securityContext": {"runAsNonRoot": True, "runAsUser": 65534,
                                    "allowPrivilegeEscalation": False,
                                    "capabilities": {"drop": ["ALL"]}}})
        init_containers.append({
            "name": "otel-collector", "image": config.METRICS_OTEL_IMAGE,
            "imagePullPolicy": "IfNotPresent",
            "restartPolicy": "Always",                  # <- makes this a native sidecar
            "args": ["--config=env:OTEL_CONFIG"],
            "env": [{"name": "OTEL_CONFIG",
                     "value": _otel_config(config.METRICS_PORT, config.METRICS_INTERVAL, netstat_target)}],
            "ports": [{"name": "metrics", "containerPort": config.METRICS_PORT}],
            "resources": {"requests": {"cpu": "50m", "memory": "64Mi"},
                          "limits": {"cpu": "200m", "memory": "128Mi"}},
            "securityContext": {"runAsNonRoot": True, "runAsUser": 65534,
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]}}})

    pod_spec = {
        # regcred = Docker Hub (isaac image); harbor-regcred = Harbor (otel-collector image).
        # Both are needed: the otel native sidecar pulls from Harbor and, being a native
        # sidecar, a 401/NotFound there would block isaac from starting.
        "imagePullSecrets": [{"name": "regcred"}, {"name": "harbor-regcred"}],
        "affinity": {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {
            "nodeSelectorTerms": [{"matchExpressions": [
                {"key": "kubernetes.io/hostname", "operator": "In", "values": nodes}]}]}}},
        "topologySpreadConstraints": [{
            "maxSkew": 1, "topologyKey": "kubernetes.io/hostname",
            "whenUnsatisfiable": "ScheduleAnyway",
            "labelSelector": {"matchLabels": {"group": config.GROUP}}}],
        "containers": containers,
        "volumes": volumes}
    if init_containers:
        pod_spec["initContainers"] = init_containers
    if config.DRA_ENABLED:
        # pod-level claim wired to the per-instance ResourceClaimTemplate; only the
        # isaac container consumes it (via resources.claims above).
        pod_spec["resourceClaims"] = [{"name": "gpu",
                                       "resourceClaimTemplateName": f"{app}-gpu"}]

    return {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": app, "namespace": config.NAMESPACE,
                     "annotations": annotations,
                     "labels": {"app": app, "group": config.GROUP}},
        "spec": {"replicas": 1, "selector": {"matchLabels": {"app": app}},
                 "template": {"metadata": {"labels": pod_labels, "annotations": pod_annotations},
                              "spec": pod_spec}}}


def workspace_pvc(name):
    """Per-instance RWO PVC for the editable workspace (only when WORKSPACE_PERSIST)."""
    app = config.PREFIX + name
    spec = {"accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": config.WORKSPACE_SIZE}}}
    if config.WORKSPACE_STORAGE_CLASS:
        spec["storageClassName"] = config.WORKSPACE_STORAGE_CLASS
    return {"apiVersion": "v1", "kind": "PersistentVolumeClaim",
            "metadata": {"name": f"{app}-workspace", "namespace": config.NAMESPACE,
                         "labels": {"app": app, "group": config.GROUP}},
            "spec": spec}


def service(name):
    """Build the per-instance LoadBalancer Service (WebRTC ports + code-server)."""
    app = config.PREFIX + name
    ports = [{"name": "http", "port": 8211, "targetPort": 8211, "protocol": "TCP"},
             {"name": "signaling", "port": 49100, "targetPort": 49100, "protocol": "TCP"},
             {"name": "media", "port": 47998, "targetPort": 47998, "protocol": "UDP"}]
    if config.CODE_SERVER_ENABLED:
        ports.append({"name": "code-server", "port": config.CODE_SERVER_PORT,
                      "targetPort": config.CODE_SERVER_CONTAINER_PORT, "protocol": "TCP"})
    return {"apiVersion": "v1", "kind": "Service",
            "metadata": {"name": f"{app}-stream", "namespace": config.NAMESPACE,
                         "labels": {"app": app, "group": config.GROUP},
                         "annotations": {"metallb.universe.tf/allow-shared-ip": f"isaac-{name}"}},
            "spec": {"type": "LoadBalancer", "externalTrafficPolicy": "Local",
                     "selector": {"app": app}, "ports": ports}}


def code_server_url(ip):
    """Browser URL for an instance's bundled VSCode (or '')."""
    return f"http://{ip}:{config.CODE_SERVER_PORT}/" if ip else ""


def lb_ip(svc):
    """LoadBalancer ingress IP of a Service object (or '')."""
    ing = (svc.get("status", {}).get("loadBalancer", {}).get("ingress", []) if svc else [])
    return ing[0].get("ip", "") if ing else ""


def advertised_ip(dep):
    """The publicEndpointAddress currently set in a Deployment's container args (or '')."""
    for a in dep["spec"]["template"]["spec"]["containers"][0].get("args", []):
        if "publicEndpointAddress=" in a:
            return a.split("=", 1)[1]
    return ""


def age(iso):
    """Humanized age from an ISO 'Z' timestamp (e.g. '2h 5m')."""
    if not iso:
        return ""
    try:
        t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return ""
    s = int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds())
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h {(s % 3600) // 60}m"
    return f"{s // 86400}d {(s % 86400) // 3600}h"
