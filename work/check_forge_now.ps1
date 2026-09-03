$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('java.exe','javaw.exe') -and $_.CommandLine -match 'forge-1.12.2-14.23.5.2860.jar.*nogui' } | Select-Object ProcessId,CreationDate,CommandLine
if ($p) { $p | ConvertTo-Json -Compress } else { '[]' }
