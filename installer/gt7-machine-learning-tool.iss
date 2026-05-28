#define MyAppName "GT7 Machine Learning Tool"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Thomas"
#define MyAppExeName "GT7-Machine-Learning-Tool.exe"

[Setup]
AppId={{3F77FCD9-6D9F-4FAF-A3D0-39806477EE65}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=GT7-Machine-Learning-Tool-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\GT7-Machine-Learning-Tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\Participant_Guide.md"; DestDir: "{app}"; DestName: "Participant_Guide.md"; Flags: ignoreversion

[Dirs]
Name: "{userdocs}\{#MyAppName}"
Name: "{userdocs}\{#MyAppName}\data"
Name: "{userdocs}\{#MyAppName}\data\runs"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{userdocs}\{#MyAppName}"
Name: "{autoprograms}\Participant Guide"; Filename: "{app}\Participant_Guide.md"
Name: "{autoprograms}\Open Collected Runs Folder"; Filename: "{userdocs}\{#MyAppName}\data\runs"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{userdocs}\{#MyAppName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
