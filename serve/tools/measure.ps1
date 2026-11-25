# serve's load test on Windows (serve/PLAN.md, Findings): for each count of idle connections,
# starts serve on a directory of a small and a larger file, holds that many idle kept-alive
# connections with tools/load, and floods it; samples the server's threads and memory (Get-Process)
# while the idle connections are held and while the flood runs. ctxlang has no way to look at
# another process's threads and memory, so this part is PowerShell.
#
#   & serve/tools/measure.ps1 [-Idle 0,100,1000] [-Clients 16] [-Seconds 10] [-Target /small.txt]
#
# from PowerShell (`powershell -File` passes `-Idle 0,100` as one string). /stats is an answer
# from memory, /small.txt (6 bytes) and /64k.bin from a file.
#
# serve/out/serve.exe and serve/out/load.exe must be built first (PLAN.md says how). The
# server's access log goes to a file, so its cost is in the numbers.

param(
    [int[]]$Idle = @(0, 100, 1000),
    [int]$Clients = 16,
    [int]$Seconds = 10,
    [string]$Target = "/small.txt",
    [int]$Port = 18090
)

$ErrorActionPreference = "Stop"
$out = Join-Path $PSScriptRoot "..\out"
$serve = Join-Path $out "serve.exe"
$load = Join-Path $out "load.exe"
$site = Join-Path $out "load-site"
New-Item -ItemType Directory -Force $site | Out-Null
[IO.File]::WriteAllBytes((Join-Path $site "small.txt"), [Text.Encoding]::ASCII.GetBytes("hello`n"))
[IO.File]::WriteAllBytes((Join-Path $site "64k.bin"), (New-Object byte[] 65536))

function Get-Sample($p) {
    $p.Refresh()
    "threads {0}, working set {1:N1} MiB, private {2:N1} MiB" -f $p.Threads.Count, ($p.WorkingSet64 / 1MB), ($p.PrivateMemorySize64 / 1MB)
}

foreach ($n in $Idle) {
    $log = Join-Path $out "load-serve-$n.log"
    $server = Start-Process -FilePath $serve -ArgumentList "`"$site`"", "--port", "$Port" -RedirectStandardOutput $log -PassThru -NoNewWindow
    Start-Sleep -Milliseconds 500
    "== idle $n, $Clients clients, $Seconds s, $Target"
    "server at start: " + (Get-Sample $server)
    $hold = 4
    $client = Start-Process -FilePath $load -ArgumentList "127.0.0.1:$Port", "--idle", "$n", "--clients", "$Clients", "--seconds", "$Seconds", "--target", $Target, "--hold", "$hold" -RedirectStandardOutput (Join-Path $out "load-client-$n.txt") -PassThru -NoNewWindow
    # Sampled while the idle connections are held (the hold), then in the middle of the flood.
    $waited = 0
    while (-not (Select-String -Path (Join-Path $out "load-client-$n.txt") -Pattern "holding|flooding" -Quiet -ErrorAction SilentlyContinue) -and $waited -lt 600) {
        Start-Sleep -Milliseconds 100
        $waited++
    }
    Start-Sleep -Seconds 2
    "server, idle held: " + (Get-Sample $server)
    Start-Sleep -Seconds ($hold - 2 + [int]($Seconds / 2))
    "server, flooding:  " + (Get-Sample $server)
    $client.WaitForExit()
    Get-Content (Join-Path $out "load-client-$n.txt") | Where-Object { $_ -notmatch "^(holding|flooding)$" }
    Stop-Process -Id $server.Id -Force
    $server.WaitForExit()
    Start-Sleep -Seconds 1
}
