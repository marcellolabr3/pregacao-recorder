param([switch]$Execute)

$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$delivery = Join-Path $project 'dist-pacote'
$cache = Join-Path $project '.bundle-cache'
$flutter = Join-Path $project 'flutter\pregacao_controle'
$flutterBuild = Join-Path $flutter 'build'
$work = Join-Path $project '.w'
$keep = @(
    'Gerador de Estudo.exe', 'Gerador de Estudo.exe.sha256',
    'Controle Android.apk', 'Controle Android.apk.sha256'
)

if (-not (Test-Path -LiteralPath (Join-Path $project 'packaging\build_release.py') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $flutter 'pubspec.yaml') -PathType Leaf)) {
    throw 'Este script precisa ficar dentro do projeto Gerador de Estudo.'
}
if ((Get-Item -LiteralPath $project -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'A raiz do projeto nao pode ser um link ou juncao.'
}

function Assert-LocalPath([string]$path) {
    $absolute = [IO.Path]::GetFullPath($path)
    if (-not $absolute.StartsWith($project + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Fora do projeto: $absolute"
    }
    $current = $absolute
    while ($current.Length -gt $project.Length) {
        $entry = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
        if ($entry -and ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Link ou juncao no caminho: $current"
        }
        $current = [IO.Path]::GetDirectoryName($current)
    }
    return $absolute
}

function Assert-TreeWithoutLinks([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { return }
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($path)
    while ($pending.Count -gt 0) {
        foreach ($item in @(Get-ChildItem -LiteralPath $pending.Pop() -Force -ErrorAction Stop)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Link ou juncao dentro de $path"
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

foreach ($name in $keep) {
    $file = Join-Path $delivery $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Entrega ausente: $file" }
}
foreach ($name in @('Gerador de Estudo.exe', 'Controle Android.apk')) {
    $file = Join-Path $delivery $name
    $recorded = (Get-Content -LiteralPath ($file + '.sha256') -Raw).Trim().Split(' ')[0]
    if ($recorded -notmatch '^[0-9a-fA-F]{64}$' -or
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $recorded) {
        throw "Hash invalido: $file"
    }
}

$targets = [Collections.Generic.List[string]]::new()
foreach ($item in @(Get-ChildItem -LiteralPath $delivery -Force)) {
    if ($item.Name -in $keep) { continue }
    if ($item.Name -eq 'installer-build' -or $item.Name -like 'personal-*' -or
        $item.Name -like 'PregacaoRecorder-*' -or $item.Name -like 'PregacaoControle-*' -or
        $item.Name -like 'build-*.log') {
        [void]$targets.Add($item.FullName)
    }
}
if (Test-Path -LiteralPath $cache -PathType Container) {
    foreach ($item in @(Get-ChildItem -LiteralPath $cache -Force)) {
        if ($item.Name -ne 'inno-7.1.0') { [void]$targets.Add($item.FullName) }
    }
}
if (Test-Path -LiteralPath $flutterBuild -PathType Container) {
    [void]$targets.Add($flutterBuild)
}
if (Test-Path -LiteralPath $work -PathType Container) {
    [void]$targets.Add($work)
}

Write-Output ("Artefatos gerados encontrados: {0}" -f $targets.Count)
$checked = [Collections.Generic.List[string]]::new()
foreach ($target in $targets) {
    $absolute = Assert-LocalPath $target
    if ($Execute) { Assert-TreeWithoutLinks $absolute }
    [void]$checked.Add($absolute)
    if ($Execute) {
        Write-Output "Verificado: $absolute"
    } else {
        Write-Output "Previa: $absolute"
    }
}
if ($Execute) {
    foreach ($absolute in $checked) {
        Write-Output "Removendo: $absolute"
        Remove-Item -LiteralPath $absolute -Recurse -Force -ErrorAction Stop
    }
} else {
    Write-Output 'Nenhum arquivo foi removido. Para executar: powershell -NoProfile -ExecutionPolicy Bypass -File packaging\limpar_gerados.ps1 -Execute'
}
