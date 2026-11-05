param([switch]$Physics, [switch]$Fdm)
$ErrorActionPreference = 'Stop'
$r2Root = $PSScriptRoot
$repoRoot = Split-Path (Split-Path $r2Root -Parent) -Parent
$cacheRoot = Join-Path $repoRoot '.build/cad'
$env:UV_CACHE_DIR = Join-Path $cacheRoot 'uv'
$env:UV_TOOL_DIR = Join-Path $cacheRoot 'tools'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $cacheRoot 'python'
$env:CADGEN_CACHE_DIR = Join-Path $cacheRoot 'store'
$env:XDG_CACHE_HOME = Join-Path $cacheRoot 'cache'
$env:MPLCONFIGDIR = Join-Path $cacheRoot 'matplotlib'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $cacheRoot 'browsers'
$requirements = Join-Path $r2Root 'requirements-dfam.txt'
function Invoke-R2Python {
    param([string[]]$ModelArguments)
    & uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.17 --with mujoco==3.17.0 --with imageio==2.37.0 --with imageio-ffmpeg==0.6.0 --with-requirements $requirements python @ModelArguments
    if ($LASTEXITCODE -ne 0) { throw "R2 command failed ($LASTEXITCODE): $($ModelArguments -join ' ')" }
}
Push-Location $repoRoot
try {
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'src/assembly.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'src/assembly_with_drag.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'src/mechanism.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'scripts/build_parts.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'src/coupons.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'scripts/export_graphics.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'scripts/check_static_interference.py'))
    Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'scripts/check_drag_fit.py'))
    if ($Fdm) { Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'scripts/measure_fdm.py')) }
    if ($Physics) {
        Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'simulation/export_r2.py'))
        Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'scripts/check_gear_mesh.py'))
        Invoke-R2Python -ModelArguments @((Join-Path $r2Root 'simulation/calibrate.py'), '--duration', '22', '--cycles', '2', '--drag-config', (Join-Path $r2Root 'config/drag_candidate.json'))
    }
}
finally { Pop-Location }
