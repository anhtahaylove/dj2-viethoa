$c=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop | Select-Object -First 1
$x=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess)
[PSCustomObject]@{PID=$x.ProcessId;Name=$x.Name;IsResourcePackHost=($x.CommandLine -match 'resourcepack-host.py');HasDJ2Pack=($x.CommandLine -match 'DJ2_Viet_Hoa_2.23.4.zip')} | ConvertTo-Json -Compress
