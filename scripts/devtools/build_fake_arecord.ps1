# Compila o simulador `arecord` para testes no Windows (sem ALSA).
# Uso: powershell -File scripts/devtools/build_fake_arecord.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bin  = Join-Path $here "bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null

$csc = @(
  "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
  "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $csc) { throw "csc.exe do .NET Framework nao encontrado" }

$out = Join-Path $bin "arecord.exe"
& $csc /nologo /optimize+ /out:$out (Join-Path $here "fake_arecord.cs")
if ($LASTEXITCODE -ne 0) { throw "falha ao compilar fake_arecord.cs" }
Write-Output "ok: $out"
