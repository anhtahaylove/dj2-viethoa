Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('java.exe','javaw.exe') } | ForEach-Object { Write-Output ('PID=' + $_.ProcessId); Write-Output $_.CommandLine }
