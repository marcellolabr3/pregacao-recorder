; Instalador pessoal: payload privado, pasta movel no SSD, sem registro local.
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
