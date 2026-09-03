$srv=@(Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('java.exe','javaw.exe')) -and ($_.CommandLine -match 'forge-1.12.2-14.23.5.2860.jar.*nogui') })
$c=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
[PSCustomObject]@{ServerCount=$srv.Count;ResourceHostPID=if($c){$c.OwningProcess}else{0}} | ConvertTo-Json -Compress
