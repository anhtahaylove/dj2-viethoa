$c=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if($c){$c|ForEach-Object{$owner=$_.OwningProcess;$proc=Get-CimInstance Win32_Process -Filter "ProcessId=$owner";[pscustomobject]@{ProcessId=$owner;Name=$proc.Name;CommandLine=$proc.CommandLine}}|ConvertTo-Json -Compress}else{'[]'}
