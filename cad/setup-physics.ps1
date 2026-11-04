$ErrorActionPreference='Stop'
$repositoryRoot=Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR=Join-Path $repositoryRoot '.build\cad\uv'
$env:UV_TOOL_DIR=Join-Path $repositoryRoot '.build\cad\tools'
$env:UV_PYTHON_INSTALL_DIR=Join-Path $repositoryRoot '.build\cad\python'
$env:XDG_CACHE_HOME=Join-Path $repositoryRoot '.build\cad\cache'
Push-Location -LiteralPath $PSScriptRoot
try{
    & uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.17 --with mujoco==3.17.0 --with imageio==2.37.0 --with imageio-ffmpeg==0.6.0 python simulation/physics.py doctor
    exit $LASTEXITCODE
}finally{Pop-Location}
