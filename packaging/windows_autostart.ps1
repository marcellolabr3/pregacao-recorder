param(
    [ValidateSet('Register', 'Enable', 'Disable', 'Resolve', 'Start', 'Status')]
    [string]$Mode = 'Status',
    [ValidateSet('Personal', 'Lab', 'Clean')]
    [string]$Layout = 'Personal',
    [string]$PackagePath = '',
    [string]$ConfigDir = '',
    [string]$StartupDir = '',
    [int]$WaitSeconds = 60
)

$ErrorActionPreference = 'Stop'
$shortcutName = if ($Layout -eq 'Clean') {
    'Gerador de Estudo.lnk'
} elseif ($Layout -eq 'Personal') {
    'Pregacao Recorder Pessoal.lnk'
} else {
    'Pregacao Recorder Laboratorio.lnk'
}
if (-not $ConfigDir) {
    $ConfigDir = if ($Layout -eq 'Clean') {
        Join-Path $env:LOCALAPPDATA 'GeradorEstudo-Autostart'
    } else {
        Join-Path $env:LOCALAPPDATA ("PregacaoRecorder-$Layout-Autostart")
    }
}
if (-not $StartupDir) {
    $StartupDir = [Environment]::GetFolderPath('Startup')
}
$ConfigDir = [IO.Path]::GetFullPath($ConfigDir)
$StartupDir = [IO.Path]::GetFullPath($StartupDir)
$configFile = Join-Path $ConfigDir 'config.json'
$localScript = Join-Path $ConfigDir 'autostart.ps1'
$shortcut = Join-Path $StartupDir $shortcutName

function Test-Package([string]$root, [string]$layoutName) {
    if ($layoutName -in @('Personal', 'Clean')) {
        return (Test-Path -LiteralPath (Join-Path $root 'package-manifest.json') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $root 'runtime\python\pythonw.exe') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $root 'gravador\app\launcher.py') -PathType Leaf)
    }
    return (Test-Path -LiteralPath (Join-Path $root '.venv\Scripts\pythonw.exe') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $root 'app\launcher.py') -PathType Leaf)
}

function Resolve-Package {
    if (-not (Test-Path -LiteralPath $configFile -PathType Leaf)) {
        throw 'Inicio automatico ainda nao registrado.'
    }
    $saved = Get-Content -LiteralPath $configFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($saved.schema_version -ne 1 -or $saved.layout -ne $Layout -or
        -not $saved.volume_serial -or -not $saved.relative_path) {
        throw 'Configuracao de inicio automatico invalida.'
    }
    $relative = [string]$saved.relative_path
    if ([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)') {
        throw 'Caminho relativo de instalacao invalido.'
    }
    foreach ($disk in @(Get-CimInstance Win32_LogicalDisk)) {
        if (-not $disk.DeviceID -or $disk.VolumeSerialNumber -ne $saved.volume_serial) {
            continue
        }
        $driveRoot = [IO.Path]::GetFullPath(([string]$disk.DeviceID + '\'))
        $candidate = [IO.Path]::GetFullPath((Join-Path $driveRoot $relative))
        if (-not $candidate.StartsWith($driveRoot, [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        if (Test-Package $candidate $Layout) {
            return $candidate
        }
    }
    throw 'Unidade da instalacao indisponivel.'
}

try {
    switch ($Mode) {
        'Register' {
            if (-not $PackagePath) { throw 'Informe -PackagePath.' }
            $packageRoot = (Resolve-Path -LiteralPath $PackagePath).Path
            if (-not (Test-Package $packageRoot $Layout)) {
                throw 'Pasta do programa incompleta para inicio automatico.'
            }
            $driveRoot = [IO.Path]::GetPathRoot($packageRoot)
            $drive = @(Get-CimInstance Win32_LogicalDisk) |
                Where-Object { $_.DeviceID -eq $driveRoot.TrimEnd('\') } |
                Select-Object -First 1
            if (-not $drive -or -not $drive.VolumeSerialNumber) {
                throw 'Nao foi possivel identificar o volume do programa.'
            }
            New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
            if ([IO.Path]::GetFullPath($PSCommandPath) -ne [IO.Path]::GetFullPath($localScript)) {
                Copy-Item -LiteralPath $PSCommandPath -Destination $localScript -Force
            }
            $saved = [ordered]@{
                schema_version = 1
                layout = $Layout
                volume_serial = [string]$drive.VolumeSerialNumber
                relative_path = $packageRoot.Substring($driveRoot.Length)
            }
            $saved | ConvertTo-Json | Set-Content -LiteralPath $configFile -Encoding UTF8
            $Mode = 'Enable'
        }
    }
    if ($Mode -eq 'Enable') {
        [void](Resolve-Package)
        New-Item -ItemType Directory -Path $StartupDir -Force | Out-Null
        $shell = New-Object -ComObject WScript.Shell
        $link = $shell.CreateShortcut($shortcut)
        $link.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $link.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
            $localScript + '" -Mode Start -Layout ' + $Layout
        $link.WorkingDirectory = $ConfigDir
        $link.WindowStyle = 7
        $link.Description = if ($Layout -eq 'Clean') { 'Iniciar Gerador de Estudo com o Windows' } else { 'Iniciar Pregacao Recorder com o Windows' }
        $link.Save()
        Write-Output 'Inicio automatico ativado.'
    } elseif ($Mode -eq 'Disable') {
        if (Test-Path -LiteralPath $shortcut -PathType Leaf) {
            Remove-Item -LiteralPath $shortcut -Force
        }
        Write-Output 'Inicio automatico desativado.'
    } elseif ($Mode -eq 'Resolve') {
        Write-Output (Resolve-Package)
    } elseif ($Mode -eq 'Status') {
        $resolved = $null
        try { $resolved = Resolve-Package } catch { }
        [pscustomobject]@{
            enabled = (Test-Path -LiteralPath $shortcut -PathType Leaf)
            package_path = $resolved
        } | ConvertTo-Json -Compress | Write-Output
    } elseif ($Mode -eq 'Start') {
        $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(0, $WaitSeconds))
        do {
            $resolved = $null
            try { $resolved = Resolve-Package } catch { }
            if ($resolved) { break }
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Unidade da instalacao indisponivel.' }
            Start-Sleep -Seconds 5
        } while ($true)
        if ($Layout -eq 'Clean') {
            Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') `
                -ArgumentList @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                    '-WindowStyle', 'Hidden', '-File', ('"' + (Join-Path $resolved 'Bandeja.ps1') + '"')) `
                -WindowStyle Hidden
            return
        }
        if ($Layout -eq 'Personal') {
            $python = Join-Path $resolved 'runtime\python\pythonw.exe'
            $working = Join-Path $resolved 'gravador'
        } else {
            $python = Join-Path $resolved '.venv\Scripts\pythonw.exe'
            $working = $resolved
        }
        Start-Process -FilePath $python -ArgumentList '-B', '-m', 'app.launcher', '--sem-navegador' -WorkingDirectory $working -WindowStyle Hidden
    }
} catch {
    if (Test-Path -LiteralPath $ConfigDir -PathType Container) {
        ('{0:s} {1}' -f [DateTime]::UtcNow, $_.Exception.Message) |
            Set-Content -LiteralPath (Join-Path $ConfigDir 'ultimo-erro.txt') -Encoding UTF8
    }
    Write-Error $_.Exception.Message
    exit 1
}
