$ErrorActionPreference='Stop'
$archiveRoot=(Resolve-Path -LiteralPath $PSScriptRoot).Path
$plan=Get-Content -Raw -LiteralPath (Join-Path $archiveRoot 'prune.json') | ConvertFrom-Json
if (-not (Test-Path -LiteralPath (Join-Path $archiveRoot 'external-copy-verification.json'))) { throw '外部复制核验未完成，禁止精简' }
$verified=Get-Content -Raw -LiteralPath (Join-Path $archiveRoot 'external-copy-verification.json') | ConvertFrom-Json
if (-not $verified.passed) { throw '外部复制核验未通过' }
$targets=foreach($entry in $plan.roots) {
    $target=[IO.Path]::GetFullPath((Join-Path $archiveRoot $entry.path))
    if (-not $target.StartsWith($archiveRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "精简路径越界：$target" }
    $resolved=(Resolve-Path -LiteralPath $target).Path
    if (-not $resolved.StartsWith($archiveRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "精简实际路径越界：$resolved" }
    $item=Get-Item -LiteralPath $resolved -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "禁止删除链接：$resolved" }
    if ($item.PSIsContainer -and (Get-ChildItem -LiteralPath $resolved -Recurse -Force -Attributes ReparsePoint | Select-Object -First 1)) { throw "精简目录内含链接：$resolved" }
    $resolved
}
foreach($target in $targets) { Remove-Item -LiteralPath $target -Recurse -Force }
Write-Output "已精简 $($plan.files) 个缓存/中间/压缩重复文件，$($plan.bytes) 字节；详细依据保存在prune.json。"
