# Yük testinin başlattığı API sürecinin toplam işlemci süresi (saniye). AI servisi kapsayıcıda ölçülür.
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$sum = 0.0
foreach ($process in Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'api-0\.0\.1-SNAPSHOT' }) {
    $running = Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    if ($running) { $sum += $running.CPU }
}
$sum.ToString($culture)
