; Instalador pessoal: payload privado no SSD e atalho de inicio por usuario.
[Setup]
AppId={{722C8AB5-104F-44A1-9797-F760FA29FA82}
AppName=Pregacao Recorder Pessoal
AppVersion={#PackageVersion}
AppPublisher=Pregacao Recorder
DefaultDirName={src}\PregacaoRecorder-Pessoal
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#InstallerOutput}
OutputBaseFilename=PregacaoRecorder-Pessoal-Instalar-{#PackageVersion}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
Uninstallable=no
CreateUninstallRegKey=no
UsePreviousAppDir=no
DisableWelcomePage=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
#include "personal-files.iss"
Source: "{#AutostartScript}"; DestDir: "{localappdata}\PregacaoRecorder-Personal-Autostart"; DestName: "autostart.ps1"; Flags: ignoreversion

[Run]
; Registra o volume e a pasta relativa. O atalho localiza o SSD pelo numero
; do volume, mesmo quando o Windows muda a letra da unidade.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{localappdata}\PregacaoRecorder-Personal-Autostart\autostart.ps1"" -Mode Register -Layout Personal -PackagePath ""{app}"""; Flags: runhidden waituntilterminated
