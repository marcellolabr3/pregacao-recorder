; Instala no PC uma copia completa da edicao pessoal atual do SSD.
[Setup]
AppId={{6A377936-1154-4243-9182-A03E19873652}
AppName=Pregacao Recorder Completo
AppVersion={#PackageVersion}
AppPublisher=Pregacao Recorder
DefaultDirName={localappdata}\PregacaoRecorder-Pessoal
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#InstallerOutput}
#ifdef SmokeTestBuild
OutputBaseFilename=PregacaoRecorder-Completo-Instalar-{#PackageVersion}-smoke
#else
OutputBaseFilename=PregacaoRecorder-Completo-Instalar-{#PackageVersion}
#endif
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
SetupMutex=PregacaoRecorderPersonalInstaller
Uninstallable=no
CreateUninstallRegKey=no
UsePreviousAppDir=no
DisableWelcomePage=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
#include "personal-files.iss"
#ifndef SmokeTestBuild
Source: "{#AutostartScript}"; DestDir: "{localappdata}\PregacaoRecorder-Personal-Autostart"; DestName: "autostart.ps1"; Flags: ignoreversion
#endif

[Icons]
#ifndef SmokeTestBuild
Name: "{userdesktop}\Pregacao Recorder Pessoal"; Filename: "{app}\Iniciar Pregacao.cmd"; WorkingDir: "{app}"; Comment: "Abrir Pregacao Recorder completo"
#endif

[Run]
#ifndef SmokeTestBuild
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{localappdata}\PregacaoRecorder-Personal-Autostart\autostart.ps1"" -Mode Register -Layout Personal -PackagePath ""{app}"""; Flags: runhidden waituntilterminated
#endif

[Code]
const
  ReparsePoint = $400;

function PathAttributes(Name: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';

procedure RequireRegularAncestors(Name: String);
var
  Parent: String;
begin
  while Name <> '' do begin
    if (PathAttributes(Name) <> $FFFFFFFF) and
       ((PathAttributes(Name) and ReparsePoint) <> 0) then
      RaiseException('A instalacao completa exige uma pasta local normal, sem links ou juncoes.');
    Parent := ExtractFileDir(Name);
    if Parent = Name then Break;
    Name := Parent;
  end;
end;

function DirectoryHasFiles(Name: String): Boolean;
var
  Found: TFindRec;
begin
  Result := False;
  if FindFirst(AddBackslash(Name) + '*', Found) then begin
    try
      repeat
        if (Found.Name <> '.') and (Found.Name <> '..') then begin
          Result := True;
          Break;
        end;
      until not FindNext(Found);
    finally
      FindClose(Found);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Root: String;
begin
  Result := '';
  try
    Root := ExpandConstant('{app}');
#ifndef SmokeTestBuild
    if CompareText(Root, ExpandConstant('{localappdata}\PregacaoRecorder-Pessoal')) <> 0 then
      RaiseException('A instalacao completa deve ficar na pasta local do usuario Windows.');
#endif
    RequireRegularAncestors(Root);
    if DirExists(Root) and DirectoryHasFiles(Root) then
      RaiseException('A pasta local ja contem arquivos. Preserve-a e use uma atualizacao, sem substituir seus dados.');
  except
    Result := GetExceptionMessage;
  end;
end;
