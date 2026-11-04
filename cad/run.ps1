param([Parameter(ValueFromRemainingArguments = $true)][string[]] $TaskArgs)
$ErrorActionPreference = 'Stop'
$cadProjectRoot = $PSScriptRoot
$repositoryRoot = Split-Path -Parent $cadProjectRoot
$env:UV_CACHE_DIR = Join-Path $repositoryRoot '.build\cad\uv'
$env:UV_TOOL_DIR = Join-Path $repositoryRoot '.build\cad\tools'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $repositoryRoot '.build\cad\python'
$env:XDG_CACHE_HOME = Join-Path $repositoryRoot '.build\cad\cache'
$env:CADGEN_CACHE_DIR = Join-Path $repositoryRoot '.build\cad\store'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $repositoryRoot '.build\cad\browsers'
$env:MPLCONFIGDIR = Join-Path $repositoryRoot '.build\cad\matplotlib'
Push-Location -LiteralPath $cadProjectRoot
try {
    if ($TaskArgs.Count -eq 0) { $TaskArgs = @('doctor') }
    & uvx --offline --no-config --managed-python --python 3.13 --from cadgen==0.7.17 python scripts/project.py @TaskArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
