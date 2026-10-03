$ErrorActionPreference = 'Stop'
$runDir = (Resolve-Path 'logs/validation/PHYS-ROT-01-T1-r1').Path
$evidenceDir = (Resolve-Path 'docs/evidence/PHYS-ROT-01/validation-T1-r1').Path
$summaryPath = Join-Path $runDir 'summary.json'
$pytestPath = Join-Path $runDir 'pytest.log'
$collectionPath = (Resolve-Path 'logs/validation/PHYS-ROT-01-T1/collection.log').Path
$monitorPath = Join-Path $evidenceDir 'monitor.jsonl'
$watch = [Diagnostics.Stopwatch]::StartNew()
$limit = [TimeSpan]::FromMinutes(35)
$reportedFailureIndices = @{ 646 = $true }

while ($watch.Elapsed -lt $limit) {
    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    $pytestLines = if (Test-Path -LiteralPath $pytestPath) { Get-Content -LiteralPath $pytestPath } else { @() }
    $progress = @($pytestLines | Where-Object { $_ -match '^([.FEsxX]+)\s*\[\s*\d+%\]' })
    $state = [pscustomobject]@{
        observed_utc = [DateTime]::UtcNow.ToString('o')
        summary_status = $summary.status
        pytest_log_bytes = if (Test-Path -LiteralPath $pytestPath) { (Get-Item -LiteralPath $pytestPath).Length } else { 0 }
        progress_lines = $progress.Count
        checks = @($summary.checks | ForEach-Object { '{0}:{1}' -f $_.name,$_.status })
    }
    $state | ConvertTo-Json -Compress -Depth 5 | Add-Content -LiteralPath $monitorPath -Encoding utf8
    Write-Output ('{0} summary={1}; pytest_bytes={2}; progress_lines={3}; checks={4}' -f `
        $state.observed_utc,$state.summary_status,$state.pytest_log_bytes,$state.progress_lines,($state.checks -join ','))

    $statusChars = [System.Collections.Generic.List[char]]::new()
    foreach ($line in $progress) {
        $match = [regex]::Match($line, '^([.FEsxX]+)\s*\[\s*\d+%\]')
        foreach ($character in $match.Groups[1].Value.ToCharArray()) { $statusChars.Add($character) }
    }
    $newFailures = @()
    for ($i = 0; $i -lt $statusChars.Count; $i++) {
        if (($statusChars[$i] -eq 'F' -or $statusChars[$i] -eq 'E') -and
            -not $reportedFailureIndices.ContainsKey($i + 1)) {
            $reportedFailureIndices[$i + 1] = $true
            $nodes = Get-Content -LiteralPath $collectionPath
            $node = if ($i -lt $nodes.Count) { $nodes[$i] } else { $null }
            $newFailures += [pscustomobject]@{
                observed_utc = [DateTime]::UtcNow.ToString('o')
                symbol = [string]$statusChars[$i]
                progress_index_zero_based = $i
                progress_index_one_based = $i + 1
                collection_node = $node
            }
        }
    }
    if ($newFailures.Count -gt 0) {
        $failurePath = Join-Path $evidenceDir 'observed-additional-failures.json'
        $existingFailures = @()
        if (Test-Path -LiteralPath $failurePath) {
            $existingFailures = @(Get-Content -LiteralPath $failurePath -Raw | ConvertFrom-Json)
        }
        @($existingFailures + $newFailures) | ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath $failurePath -Encoding utf8
        foreach ($failure in $newFailures) {
            Write-Output ('NEW_FAILURE {0} at node index {1}: {2}. Runner remains untouched.' -f `
                $failure.symbol,$failure.progress_index_one_based,$failure.collection_node)
        }
    }

    if ($summary.status -ne 'running') {
        Write-Output ('TERMINAL summary status: {0}' -f $summary.status)
        break
    }
    if ($watch.Elapsed -ge $limit) { break }
    Start-Sleep -Seconds 45
}

if ($watch.Elapsed -ge $limit) {
    [pscustomobject]@{
        observed_utc = [DateTime]::UtcNow.ToString('o')
        observation_limit_minutes = 35
        summary_status = (Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json).status
        action = 'Observation window ended; validation process left untouched.'
    } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $evidenceDir 'observation-time-limit.json') -Encoding utf8
    Write-Output 'OBSERVATION_LIMIT_REACHED; runner remains untouched.'
}
