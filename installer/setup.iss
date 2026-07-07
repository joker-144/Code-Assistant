; ──────────────────────────────────────────
; DevAgent — Inno Setup 安装脚本
; 生成标准 Windows 安装程序 (.exe)
; ──────────────────────────────────────────

#define MyAppName "DevAgent"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "DevAgent Team"
#define MyAppURL "https://github.com/dev-agent/dev-agent"
#define MyAppExeName "dev-agent.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; 安装到 Program Files\DevAgent
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; 输出目录和文件名
OutputDir=..\dist
OutputBaseFilename=DevAgent-{#MyAppVersion}-Setup
; 压缩
Compression=lzma2/max
SolidCompression=yes
; 权限
PrivilegesRequired=admin
; 主题
WizardStyle=modern
; 卸载信息
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
; 桌面快捷方式
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce
; 添加到 PATH
Name: "addtopath"; Description: "将 DevAgent 添加到系统 PATH（可在任意终端使用 dev-agent 命令）"; GroupDescription: "环境变量:"

[Files]
; 主程序
Source: "..\dist\dev-agent.exe"; DestDir: "{app}"; Flags: ignoreversion
; 环境配置模板
Source: "..\.env.example"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单 — 桌面端
Name: "{group}\DevAgent 桌面端"; Filename: "{app}\{#MyAppExeName}"; Parameters: "desktop"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
; 开始菜单 — 终端模式
Name: "{group}\DevAgent 终端"; Filename: "{cmd}"; Parameters: "/k ""{app}\{#MyAppExeName}"" --help"; WorkingDir: "{userdocs}"; IconFilename: "{app}\{#MyAppExeName}"
; 桌面快捷方式 — 桌面端
Name: "{autodesktop}\DevAgent 桌面端"; Filename: "{app}\{#MyAppExeName}"; Parameters: "desktop"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 桌面快捷方式 — 终端模式
Name: "{autodesktop}\DevAgent 终端"; Filename: "{cmd}"; Parameters: "/k ""{app}\{#MyAppExeName}"" --help"; WorkingDir: "{userdocs}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 卸载
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; 注册到 PATH（当前用户）
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Tasks: addtopath

[Run]
; 安装完成后提示 PATH 生效
Filename: "{cmd}"; Parameters: "/c echo DevAgent 安装完成！关闭并重新打开终端后即可使用 dev-agent 命令。"; Flags: nowait postinstall skipifsilent; Description: "显示使用说明"

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + UpperCase(Param) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;
