Get-CimInstance Win32_Process -Filter 'ProcessId=18084' | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | Format-List
