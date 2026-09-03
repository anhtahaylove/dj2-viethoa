$p=Get-CimInstance Win32_Process -Filter 'ProcessId=18084'
if ($p -and $p.CommandLine -match 'crash_assistant') { Stop-Process -Id 18084; 'closed' } else { 'not-closed' }
