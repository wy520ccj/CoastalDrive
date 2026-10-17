param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$archiveRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $archiveRoot '../..')).Path
$plan = Get-Content -Raw -LiteralPath (Join-Path $archiveRoot 'moves.json') | ConvertFrom-Json
$restoreMoves = foreach ($entry in $plan.roots) {
    $source = [IO.Path]::GetFullPath((Join-Path $archiveRoot $entry.archived))
    $destination = [IO.Path]::GetFullPath((Join-Path $projectRoot $entry.original))
    if (-not $source.StartsWith($archiveRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "归档路径越界：$source" }
    if (-not $destination.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $destination.StartsWith($archiveRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "恢复路径越界：$destination" }
    if (Test-Path -LiteralPath $source) {
        if (Test-Path -LiteralPath $destination) { throw "原位置已有文件，停止恢复以免覆盖：$destination" }
        [PSCustomObject]@{ Source=$source; Destination=$destination }
    }
}
Write-Output "可恢复 $($restoreMoves.Count) 个目录/文件；默认只预览，-Apply执行。精简缓存不恢复，压缩保留的日志可另行解压。"
if ($Apply) {
    foreach ($entry in $restoreMoves) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $entry.Destination) | Out-Null
        Move-Item -LiteralPath $entry.Source -Destination $entry.Destination
    }
    Write-Output '主目录归档已恢复；外部工作树按README中的git worktree move命令独立恢复。'
}
