$ErrorActionPreference = 'Stop'
$archiveRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $archiveRoot '../..')).Path
$plan = Get-Content -Raw -LiteralPath (Join-Path $archiveRoot 'moves.json') | ConvertFrom-Json
$checkedMoves = foreach ($entry in $plan.roots) {
    $source = [IO.Path]::GetFullPath((Join-Path $projectRoot $entry.original))
    $destination = [IO.Path]::GetFullPath((Join-Path $archiveRoot $entry.archived))
    if (-not $source.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $source.StartsWith($archiveRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "源路径越界：$source" }
    if (-not $destination.StartsWith($archiveRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "目标路径越界：$destination" }
    if (-not (Test-Path -LiteralPath $source) -or (Test-Path -LiteralPath $destination)) { throw "源缺失或目标已存在：$source" }
    [PSCustomObject]@{ Source = $source; Destination = $destination }
}
foreach ($entry in $checkedMoves) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $entry.Destination) | Out-Null
    Move-Item -LiteralPath $entry.Source -Destination $entry.Destination
}
Write-Output "已迁移 $($checkedMoves.Count) 个归档根项；未删除内容。"
