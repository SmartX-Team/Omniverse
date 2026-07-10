$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path run.env)) { Write-Error "run.env 없음 — cp run.env.example run.env 후 값 채우기"; exit 1 }
Get-Content run.env | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
    $v = ($matches[2] -replace '\s+#.*$','').Trim().Trim('"')
    Set-Variable -Name $matches[1] -Value $v
  }
}
if (-not $EXT_SRC_DIR)    { $EXT_SRC_DIR    = "/opt/oos_omniverse_extensions" }
if (-not $IMAGE_NAME)     { $IMAGE_NAME     = "isaac-sim" }
if (-not $IMAGE_TAG)      { $IMAGE_TAG      = "6.0" }
if (-not $GPU_DEVICE)     { $GPU_DEVICE     = "0" }
if (-not $CONTAINER_NAME) { $CONTAINER_NAME = "isaac-sim-6" }
if (-not $CACHE_ROOT)     { $CACHE_ROOT     = "$HOME/docker/isaac-sim6" }

New-Item -ItemType Directory -Force -Path `
  "$CACHE_ROOT/cache/main","$CACHE_ROOT/cache/computecache","$CACHE_ROOT/logs","$CACHE_ROOT/data","$HOME/.cache/ov/hub" | Out-Null

$envArgs = @(
  "-e","ACCEPT_EULA=Y","-e","PRIVACY_CONSENT=Y","-e","OMNI_KIT_ALLOW_ROOT=1",
  "-e","OMNI_SERVER=$OMNI_SERVER","-e","OMNI_USER=$OMNI_USER","-e","OMNI_PASS=$OMNI_PASS",
  "-e","START_GUI=$START_GUI","-e","START_WEBRTC=$START_WEBRTC",
  "-e","STARTUP_USD_STAGE=$STARTUP_USD_STAGE","-e","STARTUP_CAMERA_PATH=$STARTUP_CAMERA_PATH",
  "-e","ISAACSIM_HOST=$ISAACSIM_HOST","-e","ISAACSIM_SIGNAL_PORT=$ISAACSIM_SIGNAL_PORT","-e","ISAACSIM_STREAM_PORT=$ISAACSIM_STREAM_PORT",
  "-e","NVIDIA_DRIVER_CAPABILITIES=all","-e","EXT_SRC_DIR=$EXT_SRC_DIR","-e","EXT_PREFIX=$EXT_PREFIX"
)
$mountArgs = @()
if ($EXT_LOCAL_PATH) {
  $name = Split-Path $EXT_LOCAL_PATH -Leaf
  $mountArgs += @("-v","${EXT_LOCAL_PATH}:$EXT_SRC_DIR/${name}:ro")
}
# 이 이미지는 root 실행 → 캐시는 /root/... (5.1 캐시와 분리: isaac-sim6)
$cacheArgs = @(
  "-v","${CACHE_ROOT}/cache/main:/root/.cache:rw",
  "-v","${CACHE_ROOT}/cache/computecache:/root/.nv/ComputeCache:rw",
  "-v","${CACHE_ROOT}/logs:/root/.nvidia-omniverse/logs:rw",
  "-v","${CACHE_ROOT}/data:/root/.local/share/ov/data:rw",
  "-v","${HOME}/.cache/ov/hub:/var/cache/hub:rw"
)
docker run --rm -it --name $CONTAINER_NAME --gpus "device=$GPU_DEVICE" --network host --ipc host `
  @envArgs @mountArgs @cacheArgs "${IMAGE_NAME}:${IMAGE_TAG}"
