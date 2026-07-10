"""Kubernetes API client (official `kubernetes` library, in-cluster auth).

The ONLY module that talks to the API server. Two surfaces:

1. Low-level path facade - request/get/post/delete/patch/ok/items.
   Unchanged from the previous hand-rolled client, so every caller (instances,
   gpu, resources, tracking, policy) keeps working without edits. It now runs on
   the official client's transport, which buys us:
     - in-cluster config from the standard paths (no manual token/CA reading), AND
       periodic ServiceAccount-token refresh - the old client read the token ONCE
       at startup and would 401 after projected-token rotation (a latent bug).
     - urllib3 connection pooling + TLS verification from the cluster CA.
     - local-dev fallback to your kubeconfig (load_kube_config).

2. Higher-level helpers for the GPU-ban enforcement on a GPU-Operator cluster -
   the levers a controller (or DRA wiring) drives to make "don't allocate this GPU"
   actually stick:
     - label_node()        set nvidia.com/device-plugin.config=<name> so the
                           GPU Operator applies a per-node device-plugin config.
     - get/apply_configmap manage the device-plugin config ConfigMap (and the ban
                           store) with create-or-merge.
     - dyn()               typed access to CRDs: GPU Operator ClusterPolicy
                           (nvidia.com/v1) and, if you go the DRA route, the
                           resource.k8s.io objects (DeviceClass/ResourceClaim/Slice).
     - watch()             stream add/modify/delete events for a reconcile loop.

ENFORCEMENT NOTE: this client exposes the levers; it does not by itself stop a pod
from landing on a banned GPU. The NVIDIA device plugin has no first-class "exclude
UUID" field, so per-UUID exclusion is done node-side (a per-node device-plugin
config that limits the advertised device set, rolled out via the label above) or,
cleanly, via DRA attribute selectors. The controller that ties bans -> these calls
is separate work; see policy.py and k8s/db.
"""
import json
import logging

from kubernetes import client as kclient
from kubernetes import config as kconfig
from kubernetes import watch as kwatch
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException
from kubernetes.dynamic import DynamicClient

from . import config

log = logging.getLogger("isaac-ui.k8s")


class K8sClient:
    def __init__(self):
        try:
            kconfig.load_incluster_config()          # SA token (auto-refreshed) + CA
        except ConfigException:
            kconfig.load_kube_config()               # local development
        # Use the default Configuration the loader just set: it carries the
        # token-refresh hook (a copy would not be the one the loader updates).
        self.api = kclient.ApiClient()
        self._cfg = self.api.configuration
        # typed handles (cheap, no network; available to a controller for watches)
        self.core = kclient.CoreV1Api(self.api)
        self.apps = kclient.AppsV1Api(self.api)
        # DynamicClient does eager API discovery, so build it lazily - the facade
        # and app startup must not depend on a discovery round-trip.
        self._dynamic = None

    @property
    def dynamic(self):
        if self._dynamic is None:
            self._dynamic = DynamicClient(self.api)
        return self._dynamic

    # ----------------------------------------------------------------- transport
    def _auth_header(self):
        # auth_settings() returns the *current* token and triggers the in-cluster
        # refresh hook, so this survives projected-token rotation.
        s = self._cfg.auth_settings().get("BearerToken")
        return s["value"] if s and s.get("value") else None

    def request(self, method, path, body=None, ctype="application/json"):
        url = self._cfg.host + path
        headers = {"Accept": "application/json"}
        tok = self._auth_header()
        if tok:
            headers["Authorization"] = tok
        if body is not None:
            headers["Content-Type"] = ctype
        try:
            # Pass the Python object straight through: rest_client serializes it
            # exactly once (json.dumps, keyed off the 'json' Content-Type, and it
            # preserves a json-patch list). Pre-serializing here would double-encode
            # the body -> API server 400 "cannot unmarshal string into Go value".
            r = self.api.rest_client.request(method, url, headers=headers,
                                             body=body, _preload_content=False)
            text = r.data.decode() if r.data else ""
            return json.loads(text) if text else {}
        except ApiException as e:
            return {"_error": e.status, "_msg": (e.body or e.reason or "")}
        except Exception as e:  # network / TLS / DNS
            return {"_error": -1, "_msg": str(e)}

    # --- convenience wrappers (unchanged signatures) ---
    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body):
        return self.request("POST", path, body)

    def delete(self, path, body=None):
        return self.request("DELETE", path, body)

    def patch(self, path, body, ctype="application/json-patch+json"):
        return self.request("PATCH", path, body, ctype)

    # --- response helpers ---
    @staticmethod
    def ok(resp):
        """True when resp is a normal object (not an error envelope)."""
        return not (isinstance(resp, dict) and resp.get("_error"))

    @staticmethod
    def items(resp):
        return resp.get("items", []) if isinstance(resp, dict) else []

    # ------------------------------------------------- GPU-ban enforcement levers
    def label_node(self, name, labels):
        """Merge-patch node labels. Key lever for per-node device-plugin config:
        label_node(n, {"nvidia.com/device-plugin.config": "exclude-gpu-3"})
        makes the GPU Operator's config manager apply that named config on the node.
        Pass a label value of None to remove it."""
        return self.patch(f"/api/v1/nodes/{name}", {"metadata": {"labels": labels}},
                          ctype="application/merge-patch+json")

    def get_configmap(self, name, namespace=None):
        ns = namespace or config.NAMESPACE
        return self.get(f"/api/v1/namespaces/{ns}/configmaps/{name}")

    def apply_configmap(self, name, data, namespace=None, labels=None):
        """Create-or-merge a ConfigMap. Used for the per-node device-plugin config
        (the named configs ClusterPolicy points at) and for the ban store."""
        ns = namespace or config.NAMESPACE
        path = f"/api/v1/namespaces/{ns}/configmaps/{name}"
        body = {"data": data}
        if labels:
            body["metadata"] = {"labels": labels}
        r = self.patch(path, body, ctype="application/merge-patch+json")
        if not self.ok(r) and r.get("_error") == 404:
            r = self.post(f"/api/v1/namespaces/{ns}/configmaps",
                          {"apiVersion": "v1", "kind": "ConfigMap",
                           "metadata": {"name": name, "namespace": ns,
                                        **({"labels": labels} if labels else {})},
                           "data": data})
        return r

    def dyn(self, api_version, kind):
        """Typed accessor for any resource, including CRDs. Returns a dynamic
        Resource with .get()/.create()/.patch()/.delete()/.watch().
          gpu operator: dyn("nvidia.com/v1", "ClusterPolicy")
          DRA:          dyn("resource.k8s.io/v1", "ResourceClaimTemplate")"""
        return self.dynamic.resources.get(api_version=api_version, kind=kind)

    def watch(self, list_fn=None, *, api_version=None, kind=None,
              namespace=None, timeout_seconds=None, **kwargs):
        """Stream (event_type, object) tuples for a reconcile loop.
        Either pass a typed list fn (e.g. self.core.list_namespaced_config_map)
        with its kwargs, or api_version+kind to watch via the dynamic client."""
        if api_version and kind:
            res = self.dyn(api_version, kind)
            for ev in res.watch(namespace=namespace, timeout=timeout_seconds, **kwargs):
                yield ev["type"], ev["object"]
            return
        if list_fn is None:
            raise ValueError("watch() needs either list_fn or api_version+kind")
        w = kwatch.Watch()
        if namespace is not None:
            kwargs["namespace"] = namespace
        if timeout_seconds is not None:
            kwargs["timeout_seconds"] = timeout_seconds
        for ev in w.stream(list_fn, **kwargs):
            yield ev["type"], ev["object"]
