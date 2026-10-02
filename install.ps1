$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

$Repo = "federiconassi15/jervis"
$Base = "https://github.com/$Repo/releases/latest/download"
$Asset = "jervis-windows-x64.exe"

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Jervis requires 64-bit Windows."
}

$Temp = Join-Path ([IO.Path]::GetTempPath()) ("jervis-install-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Temp | Out-Null

try {
    $Binary = Join-Path $Temp $Asset
    $Sums = Join-Path $Temp "SHA256SUMS"

    Write-Host "Jervis: downloading $Asset..."
    Invoke-WebRequest "$Base/$Asset" -OutFile $Binary -UseBasicParsing
    Invoke-WebRequest "$Base/SHA256SUMS" -OutFile $Sums -UseBasicParsing

    $Expected = $null
    foreach ($Line in Get-Content $Sums) {
        if ($Line -match ("^([0-9a-fA-F]{64})\s+\*?" + [Regex]::Escape($Asset) + "$")) {
            $Expected = $Matches[1].ToLowerInvariant()
            break
        }
    }
    if (-not $Expected) {
        throw "Checksum entry for $Asset is missing."
    }

    $Actual = (Get-FileHash -Algorithm SHA256 $Binary).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) {
        throw "Checksum verification failed."
    }

    Write-Host ""
    Write-Host "┌─ JERVIS BOOTSTRAP ─────────────────────────────┐"
    Write-Host "│ target   $Asset"
    Write-Host "│ verify   SHA-256 ✓"
    Write-Host "│ state    native payload ready"
    Write-Host "└─ launching installation control deck ──────────┘"
    try {
        [Console]::Beep(760, 55)
        [Console]::Beep(980, 70)
    }
    catch {
        [Console]::Write("`a`a")
    }
    & $Binary
    exit $LASTEXITCODE
}
finally {
    Remove-Item -Recurse -Force $Temp -ErrorAction SilentlyContinue
}
