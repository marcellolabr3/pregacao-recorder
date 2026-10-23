; Gerado com o inventario validado por build_installer.py. Sem dados pessoais.
[Setup]
AppId={{A489FAF7-3233-45D1-B1FB-1571FD010D9B}
AppName=Gerador de Estudo
AppVersion={#PackageVersion}
AppPublisher=Gerador de Estudo
DefaultDirName={localappdata}\Gerador de Estudo
DisableDirPage=no
DisableProgramGroupPage=yes
DefaultGroupName=Gerador de Estudo
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputDir={#InstallerOutput}
#ifdef SmokeTestBuild
OutputBaseFilename=Gerador de Estudo-smoke
CreateUninstallRegKey=no
#else
OutputBaseFilename=Gerador de Estudo
#endif
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
#ifdef SmokeTestBuild
SetupMutex=GeradorEstudoSmoke-{#PackageVersion}
#else
SetupMutex=GeradorEstudoInstaller
#endif
UninstallDisplayName=Gerador de Estudo
UninstallFilesDir={app}\uninstall
DisableWelcomePage=no
UsePreviousAppDir=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "install-files.txt"; Flags: dontcopy
#include "bundle-files.iss"
#ifdef ConnectedPersonalBuild
#include "connection-files.iss"
#endif
#ifndef SmokeTestBuild
Source: "{#AutostartScript}"; DestDir: "{localappdata}\GeradorEstudo-Autostart"; DestName: "autostart.ps1"; Flags: ignoreversion
Source: "{#AppIcon}"; DestDir: "{app}"; DestName: "Gerador de Estudo.ico"; Flags: ignoreversion
#endif

[Icons]
#ifndef SmokeTestBuild
Name: "{userdesktop}\Gerador de Estudo"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: "-B -m app.launcher --abrir-painel"; WorkingDir: "{app}\gravador"; IconFilename: "{app}\Gerador de Estudo.ico"; Comment: "Abrir somente o painel no navegador"
Name: "{group}\Gerador de Estudo"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: "-B -m app.launcher --abrir-painel"; WorkingDir: "{app}\gravador"; IconFilename: "{app}\Gerador de Estudo.ico"
Name: "{group}\Desinstalar Gerador de Estudo"; Filename: "{uninstallexe}"
#endif

[Run]
#ifndef SmokeTestBuild
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{localappdata}\GeradorEstudo-Autostart\autostart.ps1"" -Mode Disable -Layout Personal"; Flags: runhidden waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{localappdata}\GeradorEstudo-Autostart\autostart.ps1"" -Mode Register -Layout Clean -PackagePath ""{app}"""; Flags: runhidden waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Bandeja.ps1"""; Flags: runhidden nowait
#endif

[UninstallRun]
#ifndef SmokeTestBuild
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{localappdata}\GeradorEstudo-Autostart\autostart.ps1"" -Mode Disable -Layout Clean"; Flags: runhidden waituntilterminated
#endif

[UninstallDelete]
#ifndef SmokeTestBuild
Type: files; Name: "{localappdata}\GeradorEstudo-Autostart\config.json"
Type: dirifempty; Name: "{localappdata}\GeradorEstudo-Autostart"
#endif

[Code]
const
  ReparsePoint = $400;
var
  InstallLock: THandle;
  Prepared: Boolean;
  BackupRoot: String;
  CreatedRoot, CreatedRecorder, CreatedLogs, CreatedLock: Boolean;
  ArchivedSources, ArchivedTargets: TArrayOfString;

function OpenInstallLock(Name: String; Access, Sharing: Cardinal; Security: NativeInt;
  Disposition, Flags: Cardinal; Template: THandle): THandle;
  external 'CreateFileW@kernel32.dll stdcall';
function CloseInstallLock(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';
function PathAttributes(Name: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';
function MoveArchivedPath(OldName, NewName: String): Boolean;
  external 'MoveFileW@kernel32.dll stdcall';

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
  if not (CreatedRoot or CreatedRecorder or CreatedLogs or CreatedLock) then Exit;
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

function WaitUntilStopped: Boolean;
var
  Attempt: Integer;
begin
  for Attempt := 1 to 12 do begin
    if not RunningInstallation then begin
      Result := True;
      Exit;
    end;
    if Attempt < 12 then Sleep(250);
  end;
  Result := False;
end;

function StopInstalledServices: Boolean;
var
  Python, ModuleFile: String;
  ExitCode: Integer;
begin
  Result := True;
  Python := ExpandConstant('{app}\runtime\python\python.exe');
  ModuleFile := ExpandConstant('{app}\gravador\app\shutdown.py');
  if not FileExists(Python) or not FileExists(ModuleFile) then Exit;
  if not Exec(Python, '-B -m app.shutdown', ExpandConstant('{app}\gravador'),
      SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
    Result := False;
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

procedure ArchivePath(Name, Relative: String);
var
  Target, Problem: String;
begin
  RequireRegularAncestors(Name);
  if not FileExists(Name) and not DirExists(Name) then Exit;
  Target := AddBackslash(BackupRoot) + Relative;
  if not ForceDirectories(ExtractFileDir(Target)) then
    RaiseException('Nao foi possivel preparar a pasta para arquivar os dados locais.');
  if not MoveArchivedPath(Name, Target) then begin
    Problem := SysErrorMessage(DLLGetLastError);
    Log('Falha ao arquivar ' + Name + ' em ' + Target + ': ' + Problem);
    RaiseException('Nao foi possivel arquivar os dados locais antes da instalacao: ' + Problem);
  end;
  SetArrayLength(ArchivedSources, GetArrayLength(ArchivedSources) + 1);
  SetArrayLength(ArchivedTargets, GetArrayLength(ArchivedTargets) + 1);
  ArchivedSources[GetArrayLength(ArchivedSources) - 1] := Name;
  ArchivedTargets[GetArrayLength(ArchivedTargets) - 1] := Target;
end;

procedure RollbackArchives;
var
  I: Integer;
begin
  for I := GetArrayLength(ArchivedSources) - 1 downto 0 do
    if FileExists(ArchivedTargets[I]) or DirExists(ArchivedTargets[I]) then
      MoveArchivedPath(ArchivedTargets[I], ArchivedSources[I]);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Root, LockName: String;
  Files: TArrayOfString;
  I: Integer;
begin
  Result := '';
  if Prepared then Exit;
  try
    Root := ExpandConstant('{app}');
    RequireRegularAncestors(Root);
    if DirExists(Root) and DirectoryHasFiles(Root)
      and not FileExists(AddBackslash(Root) + 'package-manifest.json') then begin
      if not DirExists(AddBackslash(Root) + 'gravador') then
        RaiseException('O destino ja existe sem pacote reconhecido. Escolha outra pasta.');
      if RunningInstallation then
        RaiseException('Um programa antigo ainda usa esta pasta. Encerre-o antes de instalar.');
      BackupRoot := Root + '-dados-anteriores\' + GetDateTimeString('yyyymmdd-hhnnss-zzz', '-', '-');
      RequireRegularAncestors(BackupRoot);
      if not ForceDirectories(ExtractFileDir(BackupRoot)) or not RenameFile(Root, BackupRoot) then
        RaiseException('Nao foi possivel arquivar a pasta antiga. Escolha outra pasta.');
      Log('Pasta antiga arquivada em ' + BackupRoot);
    end;
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
    if not StopInstalledServices then
      RaiseException('Ha tarefas em andamento ou o programa nao pode ser encerrado. Conclua as tarefas no painel e tente novamente.');
    if not WaitUntilStopped then
      RaiseException('O programa desta instalacao esta aberto. Conclua as tarefas e feche seus processos antes de reinstalar. Nenhum processo foi encerrado.');
    ExtractTemporaryFile('install-files.txt');
    if not LoadStringsFromFile(ExpandConstant('{tmp}\install-files.txt'), Files) then
      RaiseException('Inventario de instalacao indisponivel.');
    { Checar juncoes antes de substituir qualquer arquivo. }
    for I := 0 to GetArrayLength(Files) - 1 do
      RequireRegularAncestors(AddBackslash(Root) + Files[I]);
    if FileExists(AddBackslash(Root) + 'package-manifest.json') then begin
      BackupRoot := Root + '-dados-anteriores\' + GetDateTimeString('yyyymmdd-hhnnss-zzz', '-', '-');
      RequireRegularAncestors(BackupRoot);
      if DirExists(BackupRoot) then RaiseException('Pasta de backup ja existe; tente novamente.');
      ArchivePath(AddBackslash(Root) + 'gravador\config', 'gravador\config');
      ArchivePath(AddBackslash(Root) + 'gravador\data', 'gravador\data');
      ArchivePath(AddBackslash(Root) + 'gravador\recordings', 'gravador\recordings');
      ArchivePath(AddBackslash(Root) + 'gravador\.env', 'gravador\.env');
      ArchivePath(AddBackslash(Root) + 'pipeline\whatsapp\auth', 'pipeline\whatsapp\auth');
      ArchivePath(AddBackslash(Root) + 'pipeline\audio', 'pipeline\audio');
      ArchivePath(AddBackslash(Root) + 'pipeline\gravacoes', 'pipeline\gravacoes');
      ArchivePath(AddBackslash(Root) + 'pipeline\output', 'pipeline\output');
      ArchivePath(AddBackslash(Root) + 'pipeline\recorder\recordings', 'pipeline\recorder\recordings');
      ArchivePath(AddBackslash(Root) + 'pipeline\config.json', 'pipeline\config.json');
      ArchivePath(AddBackslash(Root) + 'pipeline\.env', 'pipeline\.env');
      if not SaveStringToFile(AddBackslash(BackupRoot) + 'LEIA-ME.txt',
        'Dados locais anteriores a esta instalacao. Podem conter gravacoes e contas.'#13#10
        + 'A instalacao nova comeca sem historico ou credenciais.'#13#10, False) then
        RaiseException('Nao foi possivel finalizar o arquivo de dados anteriores.');
      Log('Dados anteriores movidos para ' + BackupRoot);
    end;
    Prepared := True;
  except
    Result := GetExceptionMessage;
    RollbackArchives;
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
    Result := StopInstalledServices;
    if not Result then Log('A parada segura dos servicos falhou.');
    if Result then begin
      Result := WaitUntilStopped;
      if not Result then Log('Ainda ha um processo usando esta instalacao.');
    end;
    if not Result then begin
      ReleaseInstallLock;
      SuppressibleMsgBox('Conclua gravacoes, uploads e estudos antes de desinstalar. O programa sera fechado automaticamente quando estiver ocioso.', mbError, MB_OK, IDOK);
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
