param(
    [string]$LocalUrl = 'http://localhost:5173/',
    [string]$RemoteUrl = 'https://computational-social-science.github.io/globe-media-pulse/'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'
if (-not (Test-Path $frontend)) {
    Write-Error 'frontend folder not found'
}

Push-Location $frontend
try {
    if (-not (Test-Path 'node_modules')) {
        npm install
    }

    npm run build

    $nodeCommand = (Get-Command node -ErrorAction SilentlyContinue).Source
    if (-not $nodeCommand) {
        $nodeCommand = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
    }
    if (-not $nodeCommand) {
        throw 'node not found in PATH'
    }
    $viteBin = Join-Path $frontend 'node_modules\\vite\\bin\\vite.js'
    if (-not (Test-Path $viteBin)) {
        throw 'vite binary not found; ensure dependencies are installed'
    }
    $preview = Start-Process -FilePath $nodeCommand -ArgumentList @($viteBin, 'preview', '--host', '--port', '5173') -PassThru -WindowStyle Hidden
    $previewReady = $false
    for ($i = 0; $i -lt 10; $i++) {
        if ((Test-NetConnection -ComputerName localhost -Port 5173).TcpTestSucceeded) {
            $previewReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $previewReady) {
        throw 'preview server did not start on port 5173'
    }

    $local = Invoke-WebRequest -Uri $LocalUrl -UseBasicParsing
    $remote = Invoke-WebRequest -Uri $RemoteUrl -UseBasicParsing

    "LOCAL_STATUS=$($local.StatusCode)"
    "REMOTE_STATUS=$($remote.StatusCode)"
    "LOCAL_LEN=$($local.Content.Length)"
    "REMOTE_LEN=$($remote.Content.Length)"
    "LOCAL_HAS_APP=$($local.Content -match 'id=\"app\"')"
    "REMOTE_HAS_APP=$($remote.Content -match 'id=\"app\"')"

    $assetRegex = 'src=\"([^\"]+)\"|href=\"([^\"]+)\"'
    $localAssets = [regex]::Matches($local.Content, $assetRegex) |
        ForEach-Object { $_.Groups[1].Value + $_.Groups[2].Value } |
        Where-Object { $_ -and ($_ -match 'assets/|\.css$|\.js$|registerSW\.js$') } |
        Select-Object -Unique
    $remoteAssets = [regex]::Matches($remote.Content, $assetRegex) |
        ForEach-Object { $_.Groups[1].Value + $_.Groups[2].Value } |
        Where-Object { $_ -and ($_ -match 'assets/|\.css$|\.js$|registerSW\.js$') } |
        Select-Object -Unique

    "LOCAL_ASSET_COUNT=$($localAssets.Count)"
    "REMOTE_ASSET_COUNT=$($remoteAssets.Count)"

    foreach ($asset in $localAssets) {
        $url = if ($asset -match '^https?://') { $asset } else { "http://localhost:5173/$asset".Replace('//assets', '/assets') }
        $res = Invoke-WebRequest -Uri $url -UseBasicParsing
        "LOCAL_ASSET $url $($res.StatusCode)"
    }

    foreach ($asset in $remoteAssets) {
        $url = if ($asset -match '^https?://') { $asset } else { "https://computational-social-science.github.io/globe-media-pulse/$asset".Replace('//assets', '/assets') }
        $res = Invoke-WebRequest -Uri $url -UseBasicParsing
        "REMOTE_ASSET $url $($res.StatusCode)"
    }

    $apiPort = (Test-NetConnection -ComputerName localhost -Port 8000).TcpTestSucceeded
    "API_PORT_8000=$apiPort"
    if ($apiPort) {
        $health = Invoke-WebRequest -Uri 'http://localhost:8000/health/full' -UseBasicParsing
        "API_HEALTH_STATUS=$($health.StatusCode)"
    }
} finally {
    if ($preview -and -not $preview.HasExited) {
        Stop-Process -Id $preview.Id -Force
    }
    Pop-Location
}
