param([switch]$Stop)

$ErrorActionPreference = 'Stop'
$script:package = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:recorder = Join-Path $script:package 'gravador'
$script:python = Join-Path $script:package 'runtime\python\pythonw.exe'
$script:iconFile = Join-Path $script:package 'Gerador de Estudo.ico'
$script:stopFile = Join-Path $script:recorder 'logs\bandeja.parar'
$identity = [IO.Path]::GetFullPath($script:package).ToUpperInvariant()
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $suffix = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity))).Replace('-', '').Substring(0, 16)
} finally {
    $hash.Dispose()
}
$mutexName = 'Local\GeradorDeEstudoTray-' + $suffix

if ($Stop) {
    try { $running = [System.Threading.Mutex]::OpenExisting($mutexName) }
    catch [System.Threading.WaitHandleCannotBeOpenedException] { exit 0 }
    New-Item -ItemType Directory -Path (Split-Path -Parent $script:stopFile) -Force | Out-Null
    Set-Content -LiteralPath $script:stopFile -Value 'parar' -Encoding Ascii
    try {
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if (-not (Test-Path -LiteralPath $script:stopFile -PathType Leaf)) { exit 0 }
            Start-Sleep -Milliseconds 500
        }
        throw 'A bandeja nao respondeu ao pedido de encerramento.'
    } finally { $running.Dispose() }
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$created = $false
$mutex = [System.Threading.Mutex]::new($true, $mutexName, [ref]$created)
if (-not $created) {
    $mutex.Dispose()
    exit 0
}

function Start-Recorder {
    if (-not (Test-Path -LiteralPath $script:python -PathType Leaf)) { return }
    Start-Process -FilePath $script:python `
        -ArgumentList @('-B', '-m', 'app.launcher', '--sem-navegador') `
        -WorkingDirectory $script:recorder -WindowStyle Hidden
}

function Open-Panel {
    if (-not (Test-Path -LiteralPath $script:python -PathType Leaf)) { return }
    Start-Process -FilePath $script:python `
        -ArgumentList @('-B', '-m', 'app.launcher', '--abrir-painel') `
        -WorkingDirectory $script:recorder -WindowStyle Hidden
}

function Update-Health {
    $port = 8080
    $configFile = Join-Path $script:recorder 'config\config.json'
    if (Test-Path -LiteralPath $configFile -PathType Leaf) {
        try {
            $settings = Get-Content -LiteralPath $configFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($settings.web.port -and [int]$settings.web.port -ge 1 -and [int]$settings.web.port -le 65535) {
                $port = [int]$settings.web.port
            }
        } catch { }
    }
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/me" -TimeoutSec 2
        if ($null -eq $response.state) { throw 'Resposta invalida' }
        $script:icon.Icon = if ($script:healthyIcon) {
            $script:healthyIcon
        } else {
            [System.Drawing.SystemIcons]::Information
        }
        $script:icon.Text = 'Gerador de Estudo - painel ativo'
    } catch {
        $script:icon.Icon = [System.Drawing.SystemIcons]::Error
        $script:icon.Text = 'Gerador de Estudo - painel indisponivel'
    }
}

try {
    if (Test-Path -LiteralPath $script:stopFile) {
        Remove-Item -LiteralPath $script:stopFile -Force
    }
    $script:context = New-Object System.Windows.Forms.ApplicationContext
    $script:icon = New-Object System.Windows.Forms.NotifyIcon
    if (Test-Path -LiteralPath $script:iconFile -PathType Leaf) {
        $script:healthyIcon = New-Object System.Drawing.Icon($script:iconFile)
    }
    $script:icon.Icon = [System.Drawing.SystemIcons]::Application
    $script:icon.Text = 'Gerador de Estudo - iniciando'
    $menu = New-Object System.Windows.Forms.ContextMenuStrip
    [void]$menu.Items.Add('Abrir painel', $null, { Open-Panel })
    [void]$menu.Items.Add('Iniciar servico', $null, { Start-Recorder })
    [void]$menu.Items.Add('Sair da bandeja', $null, {
        $script:timer.Stop()
        $script:context.ExitThread()
    })
    $script:icon.ContextMenuStrip = $menu
    $script:icon.Add_DoubleClick({ Open-Panel })
    $script:icon.Visible = $true
    $script:timer = New-Object System.Windows.Forms.Timer
    $script:timer.Interval = 10000
    $script:timer.Add_Tick({
        if (Test-Path -LiteralPath $script:stopFile) {
            Remove-Item -LiteralPath $script:stopFile -Force
            $script:timer.Stop()
            $script:context.ExitThread()
            return
        }
        Update-Health
    })
    Start-Recorder
    Update-Health
    $script:timer.Start()
    [System.Windows.Forms.Application]::Run($script:context)
} finally {
    if ($script:timer) { $script:timer.Stop(); $script:timer.Dispose() }
    if ($script:icon) { $script:icon.Visible = $false; $script:icon.Dispose() }
    if ($script:healthyIcon) { $script:healthyIcon.Dispose() }
    if ($script:context) { $script:context.Dispose() }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
