param([switch]$Product,[string]$OutputPath='')
$ErrorActionPreference='Stop'
$devices=@(Get-CimInstance Win32_SerialPort | Where-Object {$_.PNPDeviceID -match 'VID_04B4&PID_F155'})
if($devices.Count -ne 1){throw 'Expected one VID04B4 PIDF155 KitProg3 UART'}
$port=New-Object System.IO.Ports.SerialPort($devices[0].DeviceID,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$result="KitProg3 UART $($devices[0].DeviceID)`n"
try {
 $port.Open(); Start-Sleep -Milliseconds 200; $result+=$port.ReadExisting()
 $commands=if($Product){@('watch_info','watch_probe','watch_network','watch_capture','watch_control')}else{@('watch_info','list device','lsusb -t','help')}
 foreach($command in $commands){$port.Write("$command`r`n");Start-Sleep -Milliseconds 900;$result+=$port.ReadExisting()}
}finally{if($port.IsOpen){$port.Close()};$port.Dispose();if($OutputPath){[IO.File]::WriteAllText($OutputPath,$result)}}
Write-Output $result
