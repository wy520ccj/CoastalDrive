param(
    [Parameter(Mandatory = $true)][string]$Output,
    [ValidateRange(30, 300)][int]$Seconds = 120
)

# 只采集本轮GPU/桌面合成诊断；不覆盖已有WPR采集，不修改驱动或电源设置。
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$target = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $target) { throw "证据目录已存在：$target" }
$status = & wpr -status 2>&1
if ($LASTEXITCODE -ne 0 -or ($status -join "`n") -notmatch 'WPR is not recording') {
    throw '已有WPR采集或状态无法确认，保留现有采集。'
}
New-Item -ItemType Directory -Path $target | Out-Null
$started = $false
$stopCode = $null
$runtimeCode = $null
try {
    $startText = & wpr -start GPU -start DesktopComposition -filemode 2>&1
    $startCode = $LASTEXITCODE
    $startText | Set-Content -LiteralPath (Join-Path $target 'wpr-start.log') -Encoding utf8
    if ($startCode -ne 0) {
        throw "Windows未启动GPU系统跟踪，退出码$startCode；查看wpr-start.log，权限不足时需管理员PowerShell。"
    }
    $started = $true
    $arguments = @((Join-Path $repo 'tools/performance/benchmark_runtime.py'), '--output',
        (Join-Path $target 'runtime'), '--seconds', "$Seconds", '--traffic-count', '18', '--audio', '--trace-phases')
    if ($Seconds -gt 60) { $arguments += '--extended' }
    & (Join-Path $repo '.venv/Scripts/python.exe') @arguments *> (Join-Path $target 'runtime.log')
    $runtimeCode = $LASTEXITCODE
} finally {
    if ($started) {
        & wpr -stop (Join-Path $target 'present.etl') 'CoastalDrive present wait diagnosis' *> (Join-Path $target 'wpr-stop.log')
        $stopCode = $LASTEXITCODE
    }
    [ordered]@{ started = $started; runtime_exit = $runtimeCode; stop_exit = $stopCode;
        etl_exists = (Test-Path -LiteralPath (Join-Path $target 'present.etl'));
        scope = '系统GPU/桌面合成诊断，仅本地保存；不作为无插桩性能Gate。' } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $target 'summary.json') -Encoding utf8
}
if ($stopCode -ne 0) { throw 'WPR未正常停止/保存，请查看wpr-stop.log；没有取消其他采集。' }
Write-Output "系统跟踪已保存：$(Join-Path $target 'present.etl')"
