$ErrorActionPreference='Stop'
$cadSetupRoot=$PSScriptRoot
$cadRepositoryRoot=Split-Path -Parent $cadSetupRoot
$env:UV_CACHE_DIR=Join-Path $cadRepositoryRoot '.build\cad\uv'
$env:UV_TOOL_DIR=Join-Path $cadRepositoryRoot '.build\cad\tools'
$env:UV_PYTHON_INSTALL_DIR=Join-Path $cadRepositoryRoot '.build\cad\python'
$env:CADGEN_CACHE_DIR=Join-Path $cadRepositoryRoot '.build\cad\store'
$env:PLAYWRIGHT_BROWSERS_PATH=Join-Path $cadRepositoryRoot '.build\cad\browsers'
$env:MPLCONFIGDIR=Join-Path $cadRepositoryRoot '.build\cad\matplotlib'
New-Item -ItemType Directory -Path $env:PLAYWRIGHT_BROWSERS_PATH -Force | Out-Null
Push-Location -LiteralPath $cadSetupRoot
try {
    & uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.17 cadgen doctor
    if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
    & uvx --offline --no-config --managed-python --python 3.13 --from cadgen==0.7.17 python -m playwright install --only-shell chromium
    exit $LASTEXITCODE
} finally {Pop-Location}
