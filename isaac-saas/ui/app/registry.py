"""Instance image catalog (domain layer, read-only).

Lists the container images (repo:tag) users may pick for a NEW instance, from the
configured registry. **Fails soft** like metrics.py: if the registry API is down the
UI just falls back to the server-set default image (config.IMAGE) - nothing here can
block instance creation with the default.

Adapters (config.REGISTRY_KIND):
  harbor     internal Harbor v2 API (default; lab policy: all images live in Harbor)
  dockerhub  Docker Hub v2 API (public repos, anonymous) - for a future move off-prem

SECURITY: the web layer must only accept an image that this catalog lists (or the
configured default). Users never inject arbitrary image references into pod specs.
"""
import base64
import json
import ssl
import time
import urllib.parse
import urllib.request

from . import config


def _http_json(url, user="", pw="", timeout=5):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if user:
        tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
        req.add_header("Authorization", "Basic " + tok)
    ctx = None
    if url.startswith("https://"):
        # internal registries use self-signed certs (lab posture, cf. harbor_ls.py)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


class HarborCatalog:
    name = "harbor"

    def __init__(self, base=None, project=None):
        self.base = (base or config.REGISTRY_URL).rstrip("/")
        self.project = project or config.REGISTRY_PROJECT
        self.host = self.base.split("://", 1)[-1]   # image refs carry host, no scheme

    def tags(self, repo):
        """[{tag, pushed}] for one repository (newest first by artifact push time)."""
        r = urllib.parse.quote(repo, safe="")
        arts = _http_json(f"{self.base}/api/v2.0/projects/{self.project}/repositories/"
                          f"{r}/artifacts?page_size=100&with_tag=true",
                          config.REGISTRY_USER, config.REGISTRY_PASS)
        out = []
        for a in arts:
            for t in a.get("tags") or []:
                out.append({"tag": t["name"], "pushed": a.get("push_time", "") or ""})
        return out

    def ref(self, repo, tag):
        return f"{self.host}/{self.project}/{repo}:{tag}"


class DockerHubCatalog:
    name = "dockerhub"

    def __init__(self, namespace=None):
        self.ns = namespace or config.REGISTRY_PROJECT   # Hub namespace (user/org)

    def tags(self, repo):
        data = _http_json(f"https://hub.docker.com/v2/repositories/"
                          f"{self.ns}/{repo}/tags?page_size=100")
        return [{"tag": t["name"], "pushed": t.get("tag_last_pushed", "") or ""}
                for t in data.get("results", [])]

    def ref(self, repo, tag):
        return f"docker.io/{self.ns}/{repo}:{tag}"


class RegistryService:
    """TTL-cached catalog + the ONLY validator for user-picked images."""

    def __init__(self, catalog=None, ttl=60):
        if catalog is not None:
            self.catalog = catalog
        elif config.REGISTRY_KIND == "dockerhub":
            self.catalog = DockerHubCatalog()
        else:
            self.catalog = HarborCatalog()
        self.ttl = ttl
        self._at, self._data = 0.0, None

    def images(self):
        """{available, source, default, images:[{image, repo, tag, pushed}]} - fail-soft."""
        now = time.time()
        if self._data is not None and now - self._at < self.ttl:
            return self._data
        imgs = []
        try:
            for repo in config.REGISTRY_REPOS:
                for t in self.catalog.tags(repo):
                    imgs.append({"image": self.catalog.ref(repo, t["tag"]),
                                 "repo": repo, "tag": t["tag"], "pushed": t["pushed"]})
        except Exception as e:
            # no cache on failure: recover as soon as the registry is back
            return {"available": False, "reason": str(e)[:200],
                    "source": self.catalog.name, "default": config.IMAGE, "images": []}
        imgs.sort(key=lambda x: x["pushed"], reverse=True)
        if not any(i["image"] == config.IMAGE for i in imgs):
            # default stays selectable even if it was purged from the registry
            imgs.insert(0, {"image": config.IMAGE, "repo": "", "tag": "", "pushed": ""})
        self._at, self._data = now, {"available": True, "source": self.catalog.name,
                                     "default": config.IMAGE, "images": imgs}
        return self._data

    def validate(self, image):
        """-> (ok, image|msg). '' means default. Anything else must be in the catalog
        (allow-list, not free text) - so bad/typo'd refs never reach a pod spec."""
        image = (image or "").strip()
        if not image or image == config.IMAGE:
            return True, config.IMAGE
        d = self.images()
        if not d["available"]:
            return False, f"image catalog unavailable ({d.get('reason', '')[:80]}) - " \
                          "only the default image can be used right now"
        if any(i["image"] == image for i in d["images"]):
            return True, image
        return False, "image not in the registry catalog"
