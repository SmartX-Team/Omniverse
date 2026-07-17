"""Isaac Sim self-service UI - single container, layered modules.

Layers (each depends only on the ones above it):
  config     - static configuration (env, constants, annotation schema)
  k8s        - Kubernetes REST client (the only module doing HTTP to the API)
  resources  - object-spec builders + response parse helpers (pure, no I/O)
  tracking   - metadata persistence seam (Deployment annotations today, DB later)
  instances  - instance lifecycle service (domain)
  gpu        - cluster GPU view service (domain)
  registry   - instance image catalog (Harbor/Docker Hub read API, fail-soft)
  scenes     - scene load history (stage events x DCGM GPU stats, fail-soft)
  web        - HTTP delivery (FastAPI + uvicorn), thin over the services

Run with:  python3 -m app
"""
__version__ = "0.19.0"
