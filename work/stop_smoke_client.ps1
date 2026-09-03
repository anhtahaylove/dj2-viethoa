$p = Get-CimInstance Win32_Process -Filter 'ProcessId=31948'
if ($p -and $p.Name -eq 'javaw.exe' -and $p.CommandLine -match 'launchwrapper|EntryPoint') { Stop-Process -Id 31948; Write-Output 'stopped-smoke-client' } else { Write-Output 'not-stopped' }
