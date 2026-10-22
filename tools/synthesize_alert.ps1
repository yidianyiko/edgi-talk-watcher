param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$s=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
 $s.SelectVoice('Microsoft Huihui Desktop');$s.Rate=4;$s.Volume=85
 $format=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
 $s.SetOutputToWaveFile($OutputPath,$format)
 $s.Speak('注意，看守任务已触发，请查看画面。')
 $s.SetOutputToNull()
 Write-Output 'Saved fixed Chinese event announcement, 16kHz mono PCM16'
}finally{$s.Dispose()}
