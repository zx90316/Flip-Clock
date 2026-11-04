param([switch]$Live)
$ErrorActionPreference='Stop'
$cadProjectRoot=$PSScriptRoot
$repositoryRoot=Split-Path -Parent $cadProjectRoot
$env:UV_CACHE_DIR=Join-Path $repositoryRoot '.build\cad\uv'
$env:UV_TOOL_DIR=Join-Path $repositoryRoot '.build\cad\tools'
$env:UV_PYTHON_INSTALL_DIR=Join-Path $repositoryRoot '.build\cad\python'
$env:XDG_CACHE_HOME=Join-Path $repositoryRoot '.build\cad\cache'
$pythonPath=(& uvx --offline --no-config --managed-python --python 3.13 --from cadgen==0.7.17 --with mujoco==3.17.0 --with imageio==2.37.0 --with imageio-ffmpeg==0.6.0 python -c 'import sys; print(sys.executable)' | Select-Object -Last 1).Trim()
if($LASTEXITCODE -ne 0){throw 'Physics environment unavailable. Run cad/setup-physics.ps1 first.'}
$windowPython=Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
$scriptPath=Join-Path $cadProjectRoot 'simulation\physics.py'
if($Live){$arguments=@(('"'+$scriptPath+'"'),'view')}
else{
    $pointer=Get-Content -LiteralPath (Join-Path $cadProjectRoot 'reports\physics_latest.json') -Raw | ConvertFrom-Json
    $runFolder=Join-Path $cadProjectRoot ('runs\'+$pointer.run_id)
    if(-not(Test-Path -LiteralPath (Join-Path $runFolder 'states.npz')) -and $pointer.relative_directory){$runFolder=Join-Path $cadProjectRoot $pointer.relative_directory}
    if(-not(Test-Path -LiteralPath (Join-Path $runFolder 'states.npz'))){throw 'Recorded physics data not found in this project.'}
    $arguments=@(('"'+$scriptPath+'"'),'replay','--run',('"'+$runFolder+'"'))
}
# The requested deliverable is an interactive window; pythonw avoids a console.
Start-Process -FilePath $windowPython -WorkingDirectory $cadProjectRoot -ArgumentList $arguments -WindowStyle Normal | Out-Null
