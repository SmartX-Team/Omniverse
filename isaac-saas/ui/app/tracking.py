"""Tracking-metadata seam.

Per-instance tracking (owner, description, provenance, and a free-form JSON blob) is
persisted TODAY as annotations on the Deployment, so the cluster stays the single source
of truth and there is no separate database to keep in sync.

When richer tracking is needed (status history, project/ticket links, expiry, audit
trail), replace the two functions here with a real store (ConfigMap, SQLite on a PVC, or
an external DB). Nothing above this module reads annotations directly, so only this file
changes.
"""
import json

from . import config


def build_annotations(owner="", desc="", created_at="", source="ui"):
    """Annotations to attach to a new Deployment for tracking."""
    blob = {"createdBy": source, "owner": owner, "note": desc, "createdAt": created_at}
    return {
        config.ANN_OWNER: owner,
        config.ANN_DESC: desc,
        config.ANN_CREATEDB: source,
        config.ANN_TRACKING: json.dumps(blob, ensure_ascii=False),
    }


def read(meta):
    """Extract tracking fields from a Deployment `metadata` dict."""
    ann = (meta or {}).get("annotations", {}) or {}
    try:
        blob = json.loads(ann.get(config.ANN_TRACKING, "") or "{}")
    except Exception:
        blob = {}
    return {
        "owner": ann.get(config.ANN_OWNER, ""),
        "description": ann.get(config.ANN_DESC, ""),
        "createdBy": ann.get(config.ANN_CREATEDB, ""),
        "tracking": blob,
    }
