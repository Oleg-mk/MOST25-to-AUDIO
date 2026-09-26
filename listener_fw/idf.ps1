# idf.ps1 - idf.py for this project, without export.ps1.
#   .\idf.ps1 build
#   .\idf.ps1 -p COM5 flash monitor
# ESP-IDF v6.1 in $HOME\toolchains\esp-idf and its tools in
# $HOME\toolchains\espressif, unless IDF_PATH / IDF_TOOLS_PATH say otherwise.
# Run it from PowerShell: idf_tools.py refuses MSYS / Git Bash.
if (-not $env:IDF_PATH) { $env:IDF_PATH = Join-Path $HOME "toolchains\esp-idf" }
if (-not $env:IDF_TOOLS_PATH) { $env:IDF_TOOLS_PATH = Join-Path $HOME "toolchains\espressif" }
Remove-Item Env:MSYSTEM -ErrorAction SilentlyContinue
foreach ($l in (python "$env:IDF_PATH\tools\idf_tools.py" export --format key-value 2>$null)) {
    $i = $l.IndexOf('=')
    if ($i -gt 0) {
        Set-Item -Path ("env:" + $l.Substring(0, $i)) -Value $l.Substring($i + 1).Replace('%PATH%', $env:PATH)
    }
}
Push-Location $PSScriptRoot
try { python "$env:IDF_PATH\tools\idf.py" @args } finally { Pop-Location }
exit $LASTEXITCODE
