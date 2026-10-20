; Gerado com o inventario validado por build_installer.py. Sem dados pessoais.
[Setup]
AppId={{2EA1A448-F83D-4863-9CA5-2271E17D9F67}
AppName=Pregacao Recorder
AppVersion={#PackageVersion}
AppPublisher=Pregacao Recorder
DefaultDirName={localappdata}\PregacaoRecorder
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#InstallerOutput}
#ifdef SmokeTestBuild
OutputBaseFilename=PregacaoRecorder-Instalar-{#PackageVersion}-smoke
CreateUninstallRegKey=no
#else
OutputBaseFilename=PregacaoRecorder-Instalar-{#PackageVersion}
#endif
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
SetupMutex=PregacaoRecorderPersonalInstaller
UninstallDisplayName=Pregacao Recorder
UninstallFilesDir={app}\uninstall
DisableWelcomePage=no
UsePreviousAppDir=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "install-files.txt"; Flags: dontcopy
#include "bundle-files.iss"

[Icons]
#ifndef SmokeTestBuild
Name: "{userdesktop}\Pregacao Recorder"; Filename: "{app}\Iniciar Pregacao.cmd"; WorkingDir: "{app}"; Comment: "Abrir o painel Pregacao Recorder"
#endif

[Code]
const
  ReparsePoint = $400;
var
  InstallLock: THandle;
  Prepared: Boolean;
  BackupRoot: String;
  CreatedRoot, CreatedRecorder, CreatedLogs, CreatedLock: Boolean;

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

procedure CleanupNewLockLayout;
var
  Root, Recorder, Logs: String;
begin
  if Prepared then Exit;
  Root := ExpandConstant('{app}');
  Recorder := AddBackslash(Root) + 'gravador';
  Logs := AddBackslash(Recorder) + 'logs';
  if CreatedLock then DeleteFile(AddBackslash(Logs) + 'inicializacao.lock');
  { RemoveDir remove somente diretorios vazios criados nesta tentativa. }
  if CreatedLogs then RemoveDir(Logs);
  if CreatedRecorder then RemoveDir(Recorder);
  if CreatedRoot then RemoveDir(Root);
  CreatedLock := False;
  CreatedLogs := False;
  CreatedRecorder := False;
  CreatedRoot := False;
end;

procedure RequireRegularPath(Name: String);
var
  Attr: Cardinal;
begin
  Attr := PathAttributes(Name);
  if (Attr <> $FFFFFFFF) and ((Attr and ReparsePoint) <> 0) then
    RaiseException('A instalacao nao aceita links ou juncoes no destino. Escolha uma pasta local normal.');
end;

procedure RequireRegularAncestors(Name: String);
var
  Parent: String;
begin
  while Name <> '' do begin
    RequireRegularPath(Name);
    Parent := ExtractFileDir(Name);
    if Parent = Name then Break;
    Name := Parent;
  end;
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

procedure BackupFile(Name, Relative: String);
var
  Target: String;
begin
  RequireRegularAncestors(Name);
  if not FileExists(Name) then Exit;
  Target := AddBackslash(BackupRoot) + Relative;
  if FileExists(Target) then Exit;
  if not ForceDirectories(ExtractFileDir(Target)) or not FileCopy(Name, Target, True) then
    RaiseException('Nao foi possivel concluir a copia de seguranca. Nenhum componente sera substituido.');
end;

procedure BackupTree(Name, Relative: String);
var
  Found: TFindRec;
begin
  RequireRegularAncestors(Name);
  if not DirExists(Name) then Exit;
  if FindFirst(AddBackslash(Name) + '*', Found) then begin
    try
      repeat
        if (Found.Name <> '.') and (Found.Name <> '..') then begin
          if (Found.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            BackupTree(AddBackslash(Name) + Found.Name, AddBackslash(Relative) + Found.Name)
          else
            BackupFile(AddBackslash(Name) + Found.Name, AddBackslash(Relative) + Found.Name);
        end;
      until not FindNext(Found);
    finally
      FindClose(Found);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Root, LockName, Relative: String;
  Files: TArrayOfString;
  I: Integer;
begin
  Result := '';
  if Prepared then Exit;
  try
    Root := ExpandConstant('{app}');
    RequireRegularAncestors(Root);
    if DirExists(Root) and DirectoryHasFiles(Root)
      and not FileExists(AddBackslash(Root) + 'package-manifest.json') then
      RaiseException('O destino ja existe sem pacote reconhecido. Escolha uma pasta nova.');
    LockName := AddBackslash(Root) + 'gravador\logs\inicializacao.lock';
    RequireRegularAncestors(LockName);
    CreatedRoot := not DirExists(Root);
    CreatedRecorder := not DirExists(AddBackslash(Root) + 'gravador');
    CreatedLogs := not DirExists(ExtractFileDir(LockName));
    CreatedLock := not FileExists(LockName);
    if not ForceDirectories(ExtractFileDir(LockName)) then
      RaiseException('Pasta sem permissao de escrita para este usuario.');
    InstallLock := OpenInstallLock(LockName, $C0000000, 0, 0, 4, $80, 0);
    if InstallLock = THandle(-1) then
      RaiseException('Outro iniciador ou instalador esta em uso. Feche-o e tente novamente.');
    if RunningInstallation then
      RaiseException('O programa desta instalacao esta aberto. Conclua as tarefas e feche seus processos antes de reinstalar. Nenhum processo foi encerrado.');
    ExtractTemporaryFile('install-files.txt');
    if not LoadStringsFromFile(ExpandConstant('{tmp}\install-files.txt'), Files) then
      RaiseException('Inventario de instalacao indisponivel.');
    { Checar juncoes antes de substituir qualquer arquivo. }
    for I := 0 to GetArrayLength(Files) - 1 do
      RequireRegularAncestors(AddBackslash(Root) + Files[I]);
    if FileExists(AddBackslash(Root) + 'package-manifest.json') then begin
      BackupRoot := Root + '-backups\' + GetDateTimeString('yyyymmdd-hhnnss-zzz', '-', '-');
      RequireRegularAncestors(BackupRoot);
      if DirExists(BackupRoot) then RaiseException('Pasta de backup ja existe; tente novamente.');
      for I := 0 to GetArrayLength(Files) - 1 do begin
        Relative := Files[I];
        StringChangeEx(Relative, '/', '\', True);
        BackupFile(AddBackslash(Root) + Relative, Relative);
      end;
      BackupTree(AddBackslash(Root) + 'gravador\config', 'gravador\config');
      BackupTree(AddBackslash(Root) + 'gravador\data', 'gravador\data');
      BackupTree(AddBackslash(Root) + 'pipeline\whatsapp\auth', 'pipeline\whatsapp\auth');
      BackupFile(AddBackslash(Root) + 'gravador\.env', 'gravador\.env');
      BackupFile(AddBackslash(Root) + 'pipeline\config.json', 'pipeline\config.json');
      BackupFile(AddBackslash(Root) + 'pipeline\.env', 'pipeline\.env');
      if not SaveStringToFile(AddBackslash(BackupRoot) + 'LEIA-ME.txt',
        'Copia anterior a reinstalacao. Pode conter contas e dados privados.'#13#10
        + 'Audios e gravacoes permanecem no destino original e nao sao duplicados.'#13#10, False) then
        RaiseException('Nao foi possivel finalizar a copia de seguranca.');
      Log('Copia anterior salva em ' + BackupRoot);
    end;
    Prepared := True;
  except
    Result := GetExceptionMessage;
    ReleaseInstallLock;
    CleanupNewLockLayout;
  end;
end;

procedure DeinitializeSetup;
begin
  ReleaseInstallLock;
  CleanupNewLockLayout;
end;

function InitializeUninstall: Boolean;
var
  LockName: String;
begin
  try
    LockName := ExpandConstant('{app}\gravador\logs\inicializacao.lock');
    RequireRegularAncestors(LockName);
    if not ForceDirectories(ExtractFileDir(LockName)) then
      RaiseException('Pasta de instalacao sem permissao de escrita.');
    InstallLock := OpenInstallLock(LockName, $C0000000, 0, 0, 4, $80, 0);
    if InstallLock = THandle(-1) then
      RaiseException('Outro iniciador ou instalador esta em uso.');
    Result := not RunningInstallation;
    if not Result then begin
      ReleaseInstallLock;
      SuppressibleMsgBox('Feche o programa e suas tarefas antes de desinstalar. Seus dados serao preservados.', mbError, MB_OK, IDOK);
    end;
  except
    ReleaseInstallLock;
    Result := False;
    SuppressibleMsgBox('Nao foi possivel verificar os processos. Desinstalacao cancelada.', mbError, MB_OK, IDOK);
  end;
end;

procedure DeinitializeUninstall;
begin
  ReleaseInstallLock;
end;
