param([Parameter(ValueFromRemainingArguments=$true)][string[]]$TaskArgs)
$ErrorActionPreference='Stop'
$physicsRoot=$PSScriptRoot
$repoRoot=Split-Path -Parent $physicsRoot
$env:UV_CACHE_DIR=Join-Path $repoRoot '.build\cad\uv'
$env:UV_TOOL_DIR=Join-Path $repoRoot '.build\cad\tools'
$env:UV_PYTHON_INSTALL_DIR=Join-Path $repoRoot '.build\cad\python'
$env:CADGEN_CACHE_DIR=Join-Path $repoRoot '.build\cad\store'
$env:XDG_CACHE_HOME=Join-Path $repoRoot '.build\cad\cache'
$env:MPLCONFIGDIR=Join-Path $repoRoot '.build\cad\matplotlib'
Push-Location -LiteralPath $physicsRoot
try {
    if($TaskArgs.Count -eq 0){$TaskArgs=@('view')}
    & uvx --offline --no-config --managed-python --python 3.13 --from cadgen==0.7.17 --with mujoco==3.17.0 --with imageio==2.37.0 --with imageio-ffmpeg==0.6.0 python simulation/physics.py @TaskArgs
    exit $LASTEXITCODE
} finally {Pop-Location}
