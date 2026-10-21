; Atualiza somente arquivos publicos da pasta pessoal ja instalada no SSD.
; Nenhuma conta, configuracao, banco, audio ou sessao entra neste executavel.
[Setup]
AppId={{722C8AB5-104F-44A1-9797-F760FA29FA82}
AppName=Pregacao Recorder Pessoal - Atualizacao
AppVersion={#PackageVersion}
AppPublisher=Pregacao Recorder
DefaultDirName={src}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#InstallerOutput}
OutputBaseFilename=PregacaoRecorder-Pessoal-Atualizar-{#PackageVersion}
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
Source: "update-files.txt"; Flags: dontcopy
#include "update-files.iss"
Source: "{#AutostartScript}"; DestDir: "{localappdata}\PregacaoRecorder-Personal-Autostart"; DestName: "autostart.ps1"; Flags: ignoreversion

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{localappdata}\PregacaoRecorder-Personal-Autostart\autostart.ps1"" -Mode Register -Layout Personal -PackagePath ""{app}"""; Flags: runhidden waituntilterminated

[Code]
const
  ReparsePoint = $400;
var
  InstallLock: THandle;
  BackupRoot: String;

function OpenInstallLock(Name: String; Access, Sharing: Cardinal; Security: NativeInt;
  Disposition, Flags: Cardinal; Template: THandle): THandle;
  external 'CreateFileW@kernel32.dll stdcall';
function CloseInstallLock(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';
function PathAttributes(Name: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';

procedure ReleaseInstallLock;
begin
  if (InstallLock <> 0) and (InstallLock <> THandle(-1)) then
    CloseInstallLock(InstallLock);
  InstallLock := 0;
end;

procedure RequireRegularAncestors(Name: String);
var
  Parent: String;
begin
  while Name <> '' do begin
    if (PathAttributes(Name) <> $FFFFFFFF) and
       ((PathAttributes(Name) and ReparsePoint) <> 0) then
      RaiseException('A atualizacao nao aceita links ou juncoes no destino.');
    Parent := ExtractFileDir(Name);
    if Parent = Name then Break;
    Name := Parent;
  end;
end;

function NeedsUpdate(Relative, ExpectedSHA256: String): Boolean;
var
  Target: String;
begin
  Target := AddBackslash(ExpandConstant('{app}')) + Relative;
  RequireRegularAncestors(Target);
  if not FileExists(Target) then begin
    Result := True;
    Exit;
  end;
  Result := Lowercase(GetSHA256OfFile(Target)) <> Lowercase(ExpectedSHA256);
end;

function RunningInstallation: Boolean;
var
  Locator, Services, Processes, Process: Variant;
  I: Integer;
  ExeName, Command, Root: String;
begin
  Result := False;
  Root := Lowercase(AddBackslash(ExpandConstant('{app}')));
  Locator := CreateOleObject('WbemScripting.SWbemLocator');
  Services := Locator.ConnectServer('', 'root\CIMV2');
  Processes := Services.ExecQuery('SELECT ExecutablePath, CommandLine FROM Win32_Process WHERE '
    + 'Name="python.exe" OR Name="pythonw.exe" OR Name="node.exe" OR Name="ffmpeg.exe" '
    + 'OR Name="ffprobe.exe" OR Name="chrome.exe" OR Name="chromium.exe"');
  for I := 0 to Processes.Count - 1 do begin
    Process := Processes.ItemIndex(I);
    ExeName := '';
    Command := '';
    if not VarIsNull(Process.ExecutablePath) then ExeName := Lowercase(Process.ExecutablePath);
    if not VarIsNull(Process.CommandLine) then Command := Lowercase(Process.CommandLine);
    if (Pos(Root, ExeName) = 1) or (Pos(Root, Command) > 0) then begin
      Result := True;
      Exit;
    end;
  end;
end;

procedure BackupFile(Name, Relative: String);
var
  Target: String;
begin
  RequireRegularAncestors(Name);
  if not FileExists(Name) then Exit;
  Target := AddBackslash(BackupRoot) + Relative;
  if not ForceDirectories(ExtractFileDir(Target)) or not FileCopy(Name, Target, True) then
    RaiseException('Falha na copia de seguranca; nenhum arquivo do programa foi substituido.');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Root, LockName, Relative: String;
  Files: TArrayOfString;
  I: Integer;
begin
  Result := '';
  try
    Root := ExpandConstant('{app}');
    RequireRegularAncestors(Root);
    if not FileExists(AddBackslash(Root) + 'portable-state.json') or
       not FileExists(AddBackslash(Root) + 'personal-manifest.json') or
       not FileExists(AddBackslash(Root) + 'package-manifest.json') or
       not FileExists(AddBackslash(Root) + 'gravador\data\pregacao.db') then
      RaiseException('Selecione a pasta PregacaoRecorder-Pessoal ja instalada no SSD. Nenhum dado foi alterado.');
    LockName := AddBackslash(Root) + 'gravador\logs\inicializacao.lock';
    RequireRegularAncestors(LockName);
    if not ForceDirectories(ExtractFileDir(LockName)) then
      RaiseException('Pasta sem permissao de escrita para este usuario.');
    InstallLock := OpenInstallLock(LockName, $C0000000, 0, 0, 4, $80, 0);
    if InstallLock = THandle(-1) then
      RaiseException('Outro iniciador ou instalador esta em uso. Feche-o e tente novamente.');
    if RunningInstallation then
      RaiseException('O programa esta aberto. Conclua as tarefas e feche seus processos antes de atualizar.');
    ExtractTemporaryFile('update-files.txt');
    if not LoadStringsFromFile(ExpandConstant('{tmp}\update-files.txt'), Files) then
      RaiseException('Inventario da atualizacao indisponivel.');
    BackupRoot := AddBackslash(Root) + 'gravador\recovery\update-'
      + GetDateTimeString('yyyymmdd-hhnnss-zzz', '-', '-');
    RequireRegularAncestors(BackupRoot);
    if DirExists(BackupRoot) then
      RaiseException('Pasta de copia de seguranca ja existe; tente novamente.');
    for I := 0 to GetArrayLength(Files) - 1 do begin
      Relative := Files[I];
      StringChangeEx(Relative, '/', '\', True);
      RequireRegularAncestors(AddBackslash(Root) + Relative);
      BackupFile(AddBackslash(Root) + Relative, Relative);
    end;
    if not ForceDirectories(BackupRoot) or not SaveStringToFile(
      AddBackslash(BackupRoot) + 'LEIA-ME.txt',
      'Copia dos arquivos publicos antes da atualizacao. Contas, banco e gravacoes permaneceram na pasta instalada.'#13#10,
      False) then
      RaiseException('Falha ao finalizar a copia de seguranca.');
  except
    Result := GetExceptionMessage;
    ReleaseInstallLock;
  end;
end;

procedure DeinitializeSetup;
begin
  ReleaseInstallLock;
end;
