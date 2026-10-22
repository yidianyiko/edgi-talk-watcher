param([string]$ConfigPath=(Join-Path (Split-Path $PSScriptRoot -Parent) '.env.local'),[switch]$ValidateOnly)
$ErrorActionPreference='Stop'
# Never print serial replies: the shell echoes the join command and password.
$values=@{}
foreach($line in [IO.File]::ReadAllLines($ConfigPath)) {
 if($line -match '^\s*(?:export\s+)?(WIFI_SSID|WIFI_PASSWORD)\s*=(.*)$') {
  $value=$Matches[2].Trim()
  if($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {$value=$value.Substring(1,$value.Length-2)}
  $values[$Matches[1]]=$value
 }
}
if(-not $values.ContainsKey('WIFI_SSID') -or -not $values.ContainsKey('WIFI_PASSWORD')) {throw 'Set WIFI_SSID and WIFI_PASSWORD in the private configuration file first'}
$ssid=$values['WIFI_SSID'];$password=$values['WIFI_PASSWORD']
if([Text.Encoding]::UTF8.GetByteCount($ssid) -lt 1 -or [Text.Encoding]::UTF8.GetByteCount($ssid) -gt 32 -or [Text.Encoding]::UTF8.GetByteCount($password) -gt 64 -or $ssid -match '[\x00-\x1f\x7f"\\]' -or $password -match '[\x00-\x1f\x7f"\\]') {throw 'Wi-Fi configuration cannot be represented by the current board shell'}
$command='wifi join "'+$ssid+'" "'+$password+'"'
# Verified firmware FINSH_CMD_SIZE=80; refuse truncation before opening serial.
if([Text.Encoding]::UTF8.GetByteCount($command) -ge 80) {throw 'Wi-Fi command exceeds the current board shell length; firmware extension required'}
if($ValidateOnly) {Write-Output 'Wi-Fi configuration valid; no serial access';exit 0}
$devices=@(Get-CimInstance Win32_SerialPort|Where-Object {$_.PNPDeviceID -match 'VID_04B4&PID_F155'})
if($devices.Count -ne 1) {throw 'Expected exactly one KitProg3 UART'}
$port=New-Object System.IO.Ports.SerialPort($devices[0].DeviceID,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$port.Encoding=[Text.Encoding]::UTF8
try {
 $port.Open();Start-Sleep -Milliseconds 200;$null=$port.ReadExisting()
 $port.Write("watch_info`r`n");Start-Sleep -Milliseconds 500;$info=$port.ReadExisting()
 if($info -notmatch 'WATCH INFO watch-product-(?:net|voice)-') {throw 'Network watcher firmware not detected'}
 $port.Write($command+"`r`n");$deadline=[DateTime]::UtcNow.AddSeconds(40);$connected=$false
 while([DateTime]::UtcNow -lt $deadline) {
  Start-Sleep -Seconds 2;$null=$port.ReadExisting()
  $port.Write("watch_network`r`n");Start-Sleep -Milliseconds 500;$reply=$port.ReadExisting()
  if($reply -match 'WATCH NETWORK driver=registered connected=1 ready=1') {
   $port.Write("wifi status`r`n");Start-Sleep -Milliseconds 700;$status=$port.ReadExisting()
   if($status -match ('(?m)^SSID : '+[regex]::Escape($ssid)+'\r?$')) {$connected=$true;break}
  }
 }
 if(-not $connected) {throw 'Wi-Fi did not associate with the configured network and receive an IP before timeout; no credentials were logged'}
 Write-Output 'Wi-Fi connected to the configured network; IP ready'
} finally {if($port.IsOpen){$port.Close()};$port.Dispose();$command=$null;$password=$null;$values.Clear()}
