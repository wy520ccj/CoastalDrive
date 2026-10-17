$ErrorActionPreference='Stop'
$archiveRoot=(Resolve-Path -LiteralPath $PSScriptRoot).Path
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $archiveRoot '../..')).Path
$proof=Get-Content -Raw -LiteralPath (Join-Path $archiveRoot 'external-copy-verification.json') | ConvertFrom-Json
if (-not $proof.passed) { throw '跨盘副本未通过逐文件校验' }
$entries=(Get-Content -Raw -LiteralPath (Join-Path $archiveRoot 'external.json') | ConvertFrom-Json).roots
$allowed=@('C:\Users\15120\.codex\worktrees\gr86-physics\CoastalDrive','C:\Users\15120\.codex\worktrees\simulation-fidelity\CoastalDrive')
foreach($entry in $entries) {
    if ($entry.original -notin $allowed) { continue }
    $source=(Resolve-Path -LiteralPath $entry.original).Path
    $destination=[IO.Path]::GetFullPath((Join-Path $archiveRoot $entry.archived))
    if ($source -notin $allowed -or -not $destination.StartsWith($archiveRoot+'\worktrees\',[StringComparison]::OrdinalIgnoreCase)) { throw '跨盘清理路径不符' }
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.git'))) { throw '归档缺少Git关联文件' }
    git worktree repair -- "$destination"
    if ($LASTEXITCODE -ne 0) { throw 'Git工作树关联修复失败' }
    $junction=Get-Item -LiteralPath (Join-Path $source '.venv') -Force
    if (-not ($junction.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '旧工作树.venv不是预期链接' }
    Remove-Item -LiteralPath $junction.FullName -Force
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.venv/Scripts/python.exe'))) { throw '主环境不见，停止' }
    if (Get-ChildItem -LiteralPath $source -Recurse -Force -Attributes ReparsePoint | Select-Object -First 1) { throw '源目录含未核对链接，停止清理' }
    Remove-Item -LiteralPath $source -Recurse -Force
    Write-Output "已清理通过校验的跨盘原副本：$source"
}
