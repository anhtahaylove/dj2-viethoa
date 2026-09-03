$p=Get-CimInstance Win32_Process -Filter 'ProcessId=1800'
$p | Select-Object ProcessId,ParentProcessId | Format-List
Get-CimInstance Win32_Process -Filter ('ProcessId=' + $p.ParentProcessId) | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List
