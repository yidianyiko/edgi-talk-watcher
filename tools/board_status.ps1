param(
    [ValidateSet('idle','watching','event','uncertain','paused')][string]$Status = 'idle',
    [ValidateRange(0,3600)][int]$Seconds = 0,
    [string]$PortName = '',
    [switch]$SelfTest,
    [string]$StateFile = '',
    [string]$AliveFile = '',
    [ValidateRange(1,604800)][int]$StreamSeconds = 330,
    [string]$LogPath = '',
    [string]$ControlFile = ''
)
$ErrorActionPreference = 'Stop'
$devices = @(Get-CimInstance Win32_SerialPort | Where-Object { $_.PNPDeviceID -match 'VID_04B4&PID_F155' })
if ($PortName) { $devices = @($devices | Where-Object { $_.DeviceID -eq $PortName }) }
if ($devices.Count -ne 1) { throw 'Expected exactly one KitProg3 UART; supply -PortName if multiple boards are connected.' }
$port = New-Object System.IO.Ports.SerialPort($devices[0].DeviceID,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$port.DtrEnable = $false
$port.RtsEnable = $false
$port.WriteTimeout = 1000
$script:transcript = ''
$script:recordTranscript = $true
$script:cameraRunning = $false
$script:cameraNeedsReset = $false
$script:cameraResetSupported = $false
$script:cameraRequest = ''
$script:cameraTelemetry = ''
function Camera-Reply([string]$Identity, [string]$State) {
    if (!$StateFile -or !$Identity) { return }
    $target = Join-Path (Split-Path $StateFile) 'board-camera-ack.json'
    $temporary = $target + '.tmp'
    [IO.File]::WriteAllText($temporary,(@{request_id=$Identity; status=$State} | ConvertTo-Json -Compress))
    Move-Item -LiteralPath $temporary -Destination $target -Force
}

function Read-For([int]$Milliseconds) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $result = ''
    while ($timer.ElapsedMilliseconds -lt $Milliseconds) {
        $result += $port.ReadExisting()
        Start-Sleep -Milliseconds 20
    }
    if ($script:recordTranscript) { $script:transcript += $result }
    if ($script:cameraRunning) {
        $script:cameraTelemetry += $result
        if ($script:cameraTelemetry -match 'WATCH RUN stopped calls=\d+ reason=[a-z_]+[\r\n]') {
            $script:cameraRunning = $false
            $script:cameraNeedsReset = $true
            Camera-Reply $script:cameraRequest 'stopped'
        }
        if ($script:cameraTelemetry.Length -gt 4096) { $script:cameraTelemetry = $script:cameraTelemetry.Substring($script:cameraTelemetry.Length-2048) }
    }
    return $result
}
function Command([string]$Text, [string]$Expected, [int]$TimeoutMs = 3000) {
    $null = Read-For 50
    $port.Write($Text + "`r`n")
    $result = ''
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.ElapsedMilliseconds -lt $TimeoutMs) {
        $result += Read-For 50
        if ($result -match $Expected) { return $result }
        if ($result -match 'WATCH NACK') { throw "Board rejected command: $Text" }
    }
    throw "No expected response to: $Text"
}
function Stop-Camera {
    if (!$script:cameraRunning) { return }
    $null = Command 'watch_stop' 'WATCH STOP requested[\r\n]'
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($script:cameraRunning -and $deadline.Elapsed.TotalSeconds -lt 10) { $null = Read-For 50 }
    if ($script:cameraRunning) { throw 'Board camera did not acknowledge stop within 10 seconds' }
}
function Start-Camera($Config) {
    if ([string]$Config.request_id -notmatch '^[0-9a-f]{32}$' -or
        [string]$Config.host -notmatch '^\d{1,3}(\.\d{1,3}){3}$' -or
        [int]$Config.port -lt 1 -or [int]$Config.port -gt 65535 -or
        [string]$Config.session_seed -notmatch '^[0-9a-f]{32}$' -or
        [string]$Config.task_id -notmatch '^[1-9][0-9]{0,7}$' -or
        [string]$Config.task_label -notmatch '^[A-Za-z0-9_]{1,32}$' -or
        [int]$Config.seconds -lt 1 -or [int]$Config.seconds -gt 86400 -or
        [int]$Config.interval -lt 5 -or [int]$Config.interval -gt 3600 -or
        [int]$Config.max_calls -lt 1 -or [int]$Config.max_calls -gt 1000) { throw 'Invalid board camera configuration' }
    Stop-Camera
    if ($script:cameraNeedsReset -and $script:cameraResetSupported) {
        $null = Command 'watch_camera_reset' 'WATCH CAMERA RESET ACK ready=1[\r\n]' 10000
        $script:cameraNeedsReset = $false
    }
    $null = Command ('watch_task '+[string]$Config.task_id+' '+[string]$Config.task_label) 'WATCH TASK ACK [^\r\n]+[\r\n]'
    $token = [IO.File]::ReadAllText([string]$Config.token_file).Trim()
    if ($token -notmatch '^[A-Za-z0-9_-]{32,64}$') { throw 'Invalid private camera token' }
    # UART echoes shell input, so exclude the entire provisioning exchange from logs.
    $script:recordTranscript = $false
    try {
        $null = Read-For 50
        $port.Write(('watch_gateway '+[string]$Config.host+' '+[string]$Config.port+' '+$token+' '+[string]$Config.session_seed)+"`r`n")
        $reply = ''
        $deadline = [Diagnostics.Stopwatch]::StartNew()
        while ($deadline.Elapsed.TotalSeconds -lt 3 -and $reply -notmatch 'WATCH GATEWAY ACK') { $reply += Read-For 50 }
        if ($reply -notmatch 'WATCH GATEWAY ACK') { throw 'Board rejected private camera gateway configuration' }
        $null = Read-For 100
    } finally { $script:recordTranscript = $true; $token = $null; $reply = $null }
    $script:cameraRequest = [string]$Config.request_id
    $script:cameraTelemetry = ''
    $script:cameraRunning = $true
    try {
        $null = Command ('watch_run '+[string]$Config.seconds+' '+[string]$Config.interval+' '+[string]$Config.max_calls) 'WATCH RUN ACK bounded=1[\r\n]'
    } catch {
        # A missing ACK may still mean the worker started; cancel before releasing ownership.
        try { Stop-Camera } catch { }
        $script:cameraRunning = $false
        throw 'Board camera start was not acknowledged'
    }
    if ($script:cameraRunning) { Camera-Reply $script:cameraRequest 'running' }
}
try {
    $port.Open()
    $null = Read-For 300
    $port.Write("`r`n")
    $null = Read-For 150
    $initial = Command 'watch_info' 'WATCH INFO [^\r\n]+[\r\n]'
    if ($initial -notmatch 'WATCH INFO (?:watch-screen-20261020-1|watch-product-(?:(?:net|voice)-)?20261020-[2345]|watch-product-voice-(?:20261021-[6789]|20261022-10)) (\d+) ') { throw 'Unexpected firmware version or malformed watch_info' }
    [uint64]$seq = $Matches[1]
    $productFirmware = $initial -match 'WATCH INFO watch-product-'
    $script:cameraResetSupported = $initial -match 'WATCH INFO watch-product-voice-(?:20261021-9|20261022-10) '
    # A prior bridge may already have stopped a stream before this process started.
    $script:cameraNeedsReset = $script:cameraResetSupported
    [uint64]$controlSeq = 0
    $lastTask = ''
    $lastCount = ''
    $lastAlert = ''
    if ($ControlFile -and $productFirmware) {
        if (Test-Path -LiteralPath $ControlFile) { Remove-Item -LiteralPath $ControlFile -Force }
        $baseline = Command 'watch_control' 'WATCH CONTROL \d+ [a-z]+[\r\n]'
        if ($baseline -match 'WATCH CONTROL (\d+) ') { $controlSeq = [uint64]$Matches[1] }
    }
    if ($StateFile) {
        $directory = Split-Path $StateFile
        [IO.File]::WriteAllText((Join-Path $directory 'board-ready.json'), '{"ready":true}')
        Write-Output 'BOARD READY'
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $lastSend = -1000
        $lastCameraRequest = ''
        $cameraFile = Join-Path $directory 'board-camera.json'
        while ($timer.Elapsed.TotalSeconds -lt $StreamSeconds -and !(Test-Path ($StateFile + '.stop'))) {
            if (Test-Path $StateFile) {
                $leasePath = if ($AliveFile) { $AliveFile } else { $StateFile }
                $fresh = (Test-Path $leasePath) -and (([DateTime]::UtcNow - (Get-Item $leasePath).LastWriteTimeUtc).TotalSeconds -lt 3)
                if (!$fresh -and $script:cameraRunning) { Stop-Camera }
                if ($fresh -and (Test-Path -LiteralPath $cameraFile)) {
                    $camera = Get-Content -LiteralPath $cameraFile -Raw | ConvertFrom-Json
                    $cameraIdentity = [string]$camera.request_id
                    if ($cameraIdentity -notmatch '^[0-9a-f]{32}$') { throw 'Invalid camera request identity' }
                    if ($cameraIdentity -ne $lastCameraRequest) {
                        $lastCameraRequest = $cameraIdentity
                        try {
                            if ($camera.action -eq 'start') { Start-Camera $camera; $lastTask = ([string]$camera.task_id+' '+[string]$camera.task_label) }
                            elseif ($camera.action -eq 'pause') { Stop-Camera; Camera-Reply $cameraIdentity 'stopped' }
                            else { throw 'Invalid camera action' }
                        } catch {
                            Camera-Reply $cameraIdentity 'failed'
                            Write-Output 'CAMERA request failed; configuration hidden'
                        }
                    }
                }
                if ($fresh -and $timer.ElapsedMilliseconds - $lastSend -ge 900) {
                    $desired = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
                    if ($desired.status -notin @('idle','watching','event','uncertain','paused')) { throw 'Invalid stream state' }
                    if ($productFirmware) {
                        if ($desired.PSObject.Properties.Name -contains 'task_id') {
                            $taskId = [string]$desired.task_id
                            $label = [string]$desired.task_label
                            if ($taskId -notmatch '^[1-9][0-9]{0,7}$' -or $label -notmatch '^[A-Za-z0-9_]{1,32}$') { throw 'Invalid product task' }
                            $taskKey = "$taskId $label"
                            if (!$script:cameraRunning -and $taskKey -ne $lastTask) {
                                $null = Command "watch_task $taskKey" 'WATCH TASK ACK [^\r\n]+[\r\n]'
                                $lastTask = $taskKey
                            }
                        }
                        if ($desired.PSObject.Properties.Name -contains 'event_count') {
                            $count = [string]$desired.event_count
                            if ($count -notmatch '^\d{1,10}$' -or [uint64]$count -gt 4294967295) { throw 'Invalid event count' }
                            if ($count -ne $lastCount) {
                                $null = Command "watch_count $count" "WATCH COUNT ACK $count[\r\n]"
                                $lastCount = $count
                            }
                        }
                    }
                    $seq++
                    if ($seq -gt 4294967295) { throw 'Sequence exhausted' }
                    $next = [string]$desired.status
                    if (!$script:cameraRunning) {
                        $null = Command "watch_status $seq $next" "WATCH ACK $seq $next [0-9a-f]{8}[\r\n]"
                        Write-Output "ACK $seq $next"
                    }
                    # Keep notification delivery independent of persistent event status/count.
                    if (($desired.PSObject.Properties.Name -contains 'alert_ids') -and @($desired.alert_ids).Count -gt 0) {
                        $alertId = [string]@($desired.alert_ids)[0]
                        if ($alertId -notmatch '^[0-9a-f]{32}$') { throw 'Invalid announcement identity' }
                        if ($alertId -ne $lastAlert) {
                            $reply = Command "watch_announce $alertId" 'WATCH ANNOUNCE (ACK [0-9a-f]{32} (queued|duplicate)|NACK -2)[\r\n]'
                            if ($reply -match "WATCH ANNOUNCE ACK $alertId ") { $lastAlert = $alertId; Write-Output "ANNOUNCE ACK $alertId" }
                        }
                        if ($alertId -eq $lastAlert) {
                            $ackFile = Join-Path (Split-Path $StateFile) 'board-alert-ack.json'
                            $ackTemp = "$ackFile.tmp"
                            @{alert_id=$alertId} | ConvertTo-Json -Compress | Set-Content -LiteralPath $ackTemp -Encoding ASCII
                            Move-Item -LiteralPath $ackTemp -Destination $ackFile -Force
                        }
                    }
                    $lastSend = $timer.ElapsedMilliseconds
                }
            }
            if ($ControlFile -and $productFirmware) {
                $control = Command 'watch_control' 'WATCH CONTROL \d+ [a-z]+[\r\n]'
                if ($control -match 'WATCH CONTROL (\d+) (start|pause|next|history)') {
                    [uint64]$requestId = $Matches[1]
                    $action = $Matches[2]
                    if ($requestId -gt $controlSeq) {
                        $payload = @{request_id=$requestId; action=$action} | ConvertTo-Json -Compress
                        $temporary = $ControlFile + '.tmp'
                        [IO.File]::WriteAllText($temporary,$payload)
                        Move-Item -LiteralPath $temporary -Destination $ControlFile -Force
                        $controlSeq = $requestId
                    }
                }
            }
            $null = Read-For 100
        }
        Stop-Camera
        $seq++
        $null = Command "watch_status $seq paused" "WATCH ACK $seq paused [0-9a-f]{8}[\r\n]"
        $null = Read-For 5500
        $null = Command 'watch_info' "WATCH INFO [^\r\n]+ $seq offline [0-9a-f]{8} "
        Write-Output 'BOARD STOPPED offline'
        return
    }
    $states = if ($SelfTest) { @('idle','watching','event','uncertain','paused') } else { @($Status) }
    foreach ($next in $states) {
        $seq++
        if ($seq -gt 4294967295) { throw 'Sequence exhausted; reboot board before sending further states.' }
        $null = Command "watch_status $seq $next" "WATCH ACK $seq $next [0-9a-f]{8}[\r\n]"
        Write-Output "ACK $seq $next"
    }
    if ($SelfTest) {
        $null = Command "watch_status $seq event" 'WATCH NACK -2[\r\n]'
        $badSeq = $seq + 1
        $null = Command "watch_status $badSeq nonsense" 'WATCH NACK -1[\r\n]'
        $null = Command "watch_status 4294967296 event" 'WATCH NACK -1[\r\n]'
        $null = Read-For 5500
        $final = Command 'watch_info' "WATCH INFO [^\r\n]+ $seq offline [0-9a-f]{8} "
        Write-Output 'PASS: five states, stale/invalid/overflow rejected, timeout offline'
    } elseif ($Seconds -gt 0) {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        while ($timer.Elapsed.TotalSeconds -lt $Seconds) {
            $null = Read-For 900
            $seq++
            if ($seq -gt 4294967295) { throw 'Sequence exhausted; reboot board.' }
            $null = Command "watch_status $seq $Status" "WATCH ACK $seq $Status [0-9a-f]{8}[\r\n]"
        }
    }
} finally {
    if ($port.IsOpen -and $script:cameraRunning) { try { Stop-Camera } catch { Write-Output 'CAMERA stop not acknowledged during bridge shutdown' } }
    if ($port.IsOpen) { $port.Close() }
    $port.Dispose()
    if ($LogPath) { [IO.File]::WriteAllText($LogPath,$script:transcript) }
}
