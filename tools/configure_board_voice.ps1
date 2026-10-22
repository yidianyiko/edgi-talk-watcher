param([Parameter(Mandatory=$true)][string]$ConfigPath)
$ErrorActionPreference='Stop'
$config=Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$token=[IO.File]::ReadAllText([string]$config.token_file).Trim()
$hostAddress=[string]$config.host
if($hostAddress -notmatch '^\d{1,3}(\.\d{1,3}){3}$' -or [int]$config.port -lt 1 -or [int]$config.port -gt 65535 -or $token -notmatch '^[A-Za-z0-9_-]{32,64}$') {throw 'Invalid private voice configuration'}
$devices=@(Get-CimInstance Win32_SerialPort | Where-Object {$_.PNPDeviceID -match 'VID_04B4&PID_F155'})
if($devices.Count -ne 1){throw 'Expected exactly one KitProg3 UART'}
$port=New-Object System.IO.Ports.SerialPort($devices[0].DeviceID,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
try {
 $port.Open();Start-Sleep -Milliseconds 200;$null=$port.ReadExisting()
 $port.Write("watch_info`r`n");Start-Sleep -Milliseconds 500;$info=$port.ReadExisting()
 if($info -notmatch 'WATCH INFO watch-product-voice-(?:20261020-5|(?:20261021-[6789]|20261022-10))'){throw 'Expected board voice V5, V6, V7, V8, V9 or V10 firmware'}
 $command='watch_voice_gateway '+$hostAddress+' '+[string]$config.port+' '+$token
 $port.Write($command+"`r`n");Start-Sleep -Milliseconds 700;$reply=$port.ReadExisting()
 if($reply -notmatch 'WATCH VOICE GATEWAY ACK'){throw 'Board rejected voice gateway configuration'}
 Write-Output 'Board voice gateway configured; token hidden'
}finally{if($port.IsOpen){$port.Close()};$port.Dispose();$token=$null;$command=$null;$reply=$null}
