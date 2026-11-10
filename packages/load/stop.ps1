# Yük testinin başlattığı API süreçlerini kapatır: komut satırında yük jar'ı olan ve betik başladıktan sonra
# oluşan java süreçleri. Başka bir zamanda ya da başka biçimde başlatılmış süreçlere dokunmaz.
param([Parameter(Mandatory = $true)][long]$StartedUnix)
$since = [DateTimeOffset]::FromUnixTimeSeconds($StartedUnix).LocalDateTime
Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
    Where-Object { $_.CommandLine -match 'apps[\\/]api[\\/]target[\\/]api-0\.0\.1-SNAPSHOT\.jar' -and $_.CreationDate -ge $since } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
