[CmdletBinding()]
param(
    [switch]$Once,
    [switch]$ResetLogin,
    [ValidateRange(30, 3600)]
    [int]$StatusIntervalSeconds = 120
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DataDirectory = Join-Path $ProjectRoot 'data'
$LogDirectory = Join-Path $ProjectRoot 'logs'
$SettingsPath = Join-Path $DataDirectory 'ebay-watchlist-automation.json'
$KeyPath = Join-Path $DataDirectory 'ebay-watchlist-dashboard-key.txt'
$LogPath = Join-Path $LogDirectory 'ebay-watchlist-automation.log'

New-Item -ItemType Directory -Force -Path $DataDirectory, $LogDirectory | Out-Null

function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet('INFO', 'WARNING', 'ERROR')][string]$Level = 'INFO'
    )
    $line = '{0} | {1} | {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line -ForegroundColor $(
        if ($Level -eq 'ERROR') { 'Red' }
        elseif ($Level -eq 'WARNING') { 'Yellow' }
        else { 'Gray' }
    )
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Save-Login {
    Write-Host ''
    Write-Host 'First-time connection setup' -ForegroundColor Cyan
    Write-Host 'Use the same Worker address and dashboard key shown in PokeBid Automation.'
    Write-Host 'Do not enter an eBay client secret or eBay refresh token here.' -ForegroundColor Yellow
    Write-Host ''

    $endpoint = (Read-Host 'Worker HTTPS address').Trim().TrimEnd('/')
    if ($endpoint -notmatch '^https://[^/]+(?:/.*)?$' -and $endpoint -notmatch '^http://localhost(?::\d+)?(?:/.*)?$') {
        throw 'The Worker address must be a valid HTTPS URL (or localhost for testing).'
    }

    $secureKey = Read-Host 'PokéBid dashboard key' -AsSecureString
    if ($secureKey.Length -lt 8) {
        throw 'The dashboard key appears to be empty or too short.'
    }

    @{ endpoint = $endpoint } | ConvertTo-Json | Set-Content -LiteralPath $SettingsPath -Encoding UTF8
    $secureKey | ConvertFrom-SecureString | Set-Content -LiteralPath $KeyPath -Encoding ASCII
    Write-Log 'Connection settings saved. The dashboard key is encrypted for this Windows user.'
}

function Get-Login {
    if (-not (Test-Path -LiteralPath $SettingsPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
        Save-Login
    }

    $settings = Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
    $encryptedKey = (Get-Content -LiteralPath $KeyPath -Raw).Trim()
    $secureKey = $encryptedKey | ConvertTo-SecureString
    $credential = [pscredential]::new('pokebid', $secureKey)
    $plainKey = $credential.GetNetworkCredential().Password

    if ([string]::IsNullOrWhiteSpace($settings.endpoint) -or [string]::IsNullOrWhiteSpace($plainKey)) {
        throw 'Saved login is incomplete. Run reset-ebay-watchlist-automation-login.bat.'
    }

    return [pscustomobject]@{
        Endpoint = ([string]$settings.endpoint).TrimEnd('/')
        ApiKey = $plainKey
    }
}

function Invoke-PokeBidApi {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [ValidateSet('GET', 'POST')][string]$Method = 'GET',
        [object]$Body = $null,
        [int]$TimeoutSeconds = 45
    )

    $headers = @{ Authorization = 'Bearer ' + $script:Login.ApiKey }
    $parameters = @{
        Uri = $script:Login.Endpoint + $Path
        Method = $Method
        Headers = $headers
        TimeoutSec = $TimeoutSeconds
        UseBasicParsing = $true
    }
    if ($Method -eq 'POST') {
        $parameters.ContentType = 'application/json'
        $parameters.Body = if ($null -eq $Body) { '{}' } else { $Body | ConvertTo-Json -Compress }
    }

    try {
        return Invoke-RestMethod @parameters
    }
    catch {
        $detail = $_.Exception.Message
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $detail = $_.ErrorDetails.Message
        }
        throw ('Worker request {0} {1} failed: {2}' -f $Method, $Path, $detail)
    }
}

function Show-Status {
    $status = Invoke-PokeBidApi -Path '/api/status'
    $latest = $status.latest
    $lastCompleted = if ($latest -and $latest.completed_at) { [string]$latest.completed_at } else { 'not completed yet' }
    $rules = if ($null -ne $status.active_rules) { $status.active_rules } else { 0 }
    $matches = if ($null -ne $status.total_matches) { $status.total_matches } else { 0 }
    $watchlisted = if ($null -ne $status.watchlisted) { $status.watchlisted } else { 0 }
    $failed = if ($null -ne $status.failed) { $status.failed } else { 0 }
    $searched = if ($latest -and $null -ne $latest.searched) { $latest.searched } else { 0 }
    $newMatches = if ($latest -and $null -ne $latest.matches) { $latest.matches } else { 0 }
    $state = if ($status.enabled -eq $false) { 'PAUSED' } else { 'LIVE' }
    $policy = if ($status.matching_policy) { [string]$status.matching_policy } else { 'legacy or unknown' }
    $lastSearch = if ($status.last_search) { [string]$status.last_search } else { 'not reported' }

    Write-Log ("STATUS={0} | policy={1} | last search={2} | saved searches={3} | last scan={4} | listings checked={5} | new matches={6} | all matches={7} | watchlisted={8} | failed={9}" -f $state, $policy, $lastSearch, $rules, $lastCompleted, $searched, $newMatches, $matches, $watchlisted, $failed)
    if ($policy -ne 'name-and-number; all prices; UK-located; round-robin; max-10') {
        Write-Log 'The deployed Worker does not report the UK round-robin max-10 policy. Deploy the latest Worker update before relying on this BAT.' 'WARNING'
    }
}

try {
    if ($ResetLogin) {
        Remove-Item -LiteralPath $SettingsPath, $KeyPath -Force -ErrorAction SilentlyContinue
        Write-Log 'Saved Worker address and encrypted dashboard key removed.'
        exit 0
    }

    $script:Login = Get-Login
    Write-Log ('Connecting to ' + $script:Login.Endpoint)

    $sync = Invoke-PokeBidApi -Path '/api/rules/sync' -Method POST
    $eligibleRules = if ($null -ne $sync.eligibleRules) { $sync.eligibleRules } else { 0 }
    Write-Log ("SAVED SEARCH SYNC | {0} target-labelled searches loaded" -f $eligibleRules)

    $enable = Invoke-PokeBidApi -Path '/api/automation' -Method POST -Body @{ enabled = $true }
    if ($enable.enabled -eq $false) {
        throw 'The Worker did not confirm that automation is enabled.'
    }
    Write-Log 'AUTOMATION ENABLED | One Saved Search every two minutes, rotating through all searches'

    $scan = Invoke-PokeBidApi -Path '/api/scan' -Method POST -TimeoutSeconds 60
    Write-Log 'IMMEDIATE SCAN QUEUED | UK title matches at every price; maximum 10 additions for this search'
    Start-Sleep -Seconds 8
    Show-Status

    if ($Once) {
        exit 0
    }

    Write-Host ''
    Write-Host ('Monitoring every {0} seconds. The Worker performs the scans in the cloud.' -f $StatusIntervalSeconds) -ForegroundColor Cyan
    Write-Host 'You may close this window; automation will remain enabled.' -ForegroundColor Cyan
    Write-Host ''

    while ($true) {
        Start-Sleep -Seconds $StatusIntervalSeconds
        try {
            Show-Status
        }
        catch {
            Write-Log $_.Exception.Message 'WARNING'
        }
    }
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    Write-Host ''
    Write-Host 'If the address or key is wrong, run reset-ebay-watchlist-automation-login.bat.' -ForegroundColor Yellow
    exit 1
}
