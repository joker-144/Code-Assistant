; Inno Setup Script for DevAgent Desktop (Electron-based)
; Packages the Electron build output from dist-electron/

#define AppName "DevAgent"
#define AppVersion GetFileVersion("..\dist-electron\win-unpacked\DevAgent.exe")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B8F3A1D2-6E5C-4A9B-8D7F-1C3E5A7B9D0F}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=DevAgent Team
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist-installer
OutputBaseFilename=DevAgent-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=log.ico
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Main Electron application (unpacked build)
Source: "..\dist-electron\win-unpacked\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Backend executable (bundled in Electron's resources)
; Already included via recursesubdirs above, as it lives under resources/backend/

[Dirs]
; Ensure backend directory exists
Name: "{app}\resources\backend"

[Icons]
; Desktop shortcut → Electron exe
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DevAgent.exe"; Tasks: desktopicon
; Start Menu shortcut
Name: "{group}\{#AppName}"; Filename: "{app}\DevAgent.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Optionally launch after install
Filename: "{app}\DevAgent.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\DevAgent"
