; Built by build.ps1, which passes the payload directory in. Nothing here reaches into the repo.
#define MyAppName "Claude Sweeper"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Toby Kalkman"
#define MyAppURL "https://github.com/TK9443/claude-sweeper"
#define MyAppExeName "ClaudeSweeper.exe"
#ifndef PayloadDir
  #define PayloadDir "..\dist\ClaudeSweeper"
#endif

[Setup]
AppId={{3B8E6D2A-9C41-4F57-A2D0-6E1F7B94C5A3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\installer
OutputBaseFilename=ClaudeSweeper-Setup
SetupIconFile=..\assets\claude-sweeper.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[InstallDelete]
; Inno overwrites but never removes, so the bundled runtime is wiped first.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Start Menu and desktop. Autostart is deliberately absent.
[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
