$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$shinsuPython = 'C:/Users/AI-00/anaconda3/envs/torch-gpu-126/python.exe'
if (-not (Test-Path -LiteralPath $shinsuPython)) {
    $shinsuPython = 'C:/Users/wmwm1/OneDrive/Desktop/work/.venv/Scripts/python.exe'
}
if (-not (Test-Path -LiteralPath $shinsuPython)) { throw '지정된 파이썬 환경을 찾지 못했습니다.' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
& $shinsuPython -X utf8 -m shisu run
exit $LASTEXITCODE
