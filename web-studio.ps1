$ErrorActionPreference = 'Stop'
$pythonPath = $env:MUSIC_STUDIO_PYTHON
if (-not $pythonPath) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $pythonPath = $bundledPython }
    else { $pythonPath = 'python' }
}
& $pythonPath (Join-Path $PSScriptRoot 'web_studio.py') @args
exit $LASTEXITCODE
