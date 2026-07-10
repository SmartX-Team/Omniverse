$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Test-Path build.env) {
  Get-Content build.env | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
      $v = ($matches[2] -replace '\s+#.*$','').Trim().Trim('"')
      Set-Variable -Name $matches[1] -Value $v
    }
  }
}
if (-not $EXT_REPO_URLS) { $EXT_REPO_URLS = "" }
if (-not $EXT_SRC_DIR)   { $EXT_SRC_DIR   = "/opt/oos_omniverse_extensions" }
if (-not $IMAGE_NAME)    { $IMAGE_NAME    = "isaac-sim" }
if (-not $IMAGE_TAG)     { $IMAGE_TAG     = "6.0" }
if (-not $BUILD_ROS_WS)  { $BUILD_ROS_WS  = "0" }
docker build --build-arg EXT_REPO_URLS="$EXT_REPO_URLS" --build-arg EXT_SRC_DIR="$EXT_SRC_DIR" --build-arg BUILD_ROS_WS="$BUILD_ROS_WS" -t "${IMAGE_NAME}:${IMAGE_TAG}" .
