param([string]$LogPath='')
$ErrorActionPreference='Stop'
$devices=@(Get-CimInstance Win32_SerialPort|Where-Object {$_.PNPDeviceID -match 'VID_04B4&PID_F155'})
if($devices.Count -ne 1){throw 'Expected one KitProg3 UART'}
$port=New-Object System.IO.Ports.SerialPort($devices[0].DeviceID,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$log=''
function Check([string]$Command,[string]$Pattern){
 $port.Write("$Command`r`n");$timer=[Diagnostics.Stopwatch]::StartNew();$reply=''
 while($timer.ElapsedMilliseconds -lt 3500){Start-Sleep -Milliseconds 30;$reply+=$port.ReadExisting();if($reply -match $Pattern){$script:log+=$reply;return $reply}}
 $script:log+=$reply;throw "Unexpected board response: $Command"
}
try{
 $port.Open();Start-Sleep -Milliseconds 200;$log+=$port.ReadExisting()
 $null=Check 'watch_info' 'WATCH INFO watch-product-(?:net-)?20261020-[234] '
 $null=Check 'watch_task 12 PERSON_APPEARS' 'WATCH TASK ACK 12 PERSON_APPEARS'
 $null=Check 'watch_info' ' 12 paused | paused [0-9a-f]{8} '
 $null=Check 'watch_count 17' 'WATCH COUNT ACK 17'
 $null=Check 'watch_task 0 BAD' 'WATCH TASK NACK 12 PERSON_APPEARS'
 $null=Check 'watch_count 4294967296' 'WATCH COUNT NACK 17'
 $baseline=Check 'watch_control' 'WATCH CONTROL (\d+) [a-z]+'
 if($baseline -notmatch 'WATCH CONTROL (\d+) '){throw 'Missing baseline'}
 [uint64]$request=[uint64]$Matches[1]
 foreach($action in @('start','pause','next','history')){
  $request++;$null=Check "watch_action $action" "WATCH ACTION $request $action"
  $null=Check 'watch_control' "WATCH CONTROL $request $action"
 }
 $null=Check 'watch_action erase' 'WATCH ACTION NACK'
 $null=Check 'watch_probe' 'WATCH CAP uvc='
 $null=Check 'watch_network' 'WATCH NETWORK '
 Write-Output 'PASS: task, count, invalid inputs, four user requests, capability and network reporting'
}finally{if($port.IsOpen){$port.Close()};$port.Dispose();if($LogPath){[IO.File]::WriteAllText($LogPath,$log)}}
