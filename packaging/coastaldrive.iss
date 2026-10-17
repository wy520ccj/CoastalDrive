; 按当前用户安装；卸载只处理安装文件，不删除工程记录和成绩。
#ifndef PackageDir
  #error PackageDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif
#define AppVersion "0.9.0-dev.20261017"
#define RepoRoot SourcePath + ".."

[Setup]
AppId={{C53A2791-24D5-4BB5-8351-D2D683E3C8E8}
AppName=CoastalDrive
AppVersion={#AppVersion}
AppVerName=CoastalDrive {#AppVersion} (开发试玩版)
AppPublisher=CoastalDrive contributors
AppPublisherURL=https://github.com/wy520ccj/CoastalDrive
AppSupportURL=https://github.com/wy520ccj/CoastalDrive/issues
AppUpdatesURL=https://github.com/wy520ccj/CoastalDrive/releases
DefaultDirName={localappdata}\Programs\CoastalDrive
DefaultGroupName=CoastalDrive
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=CoastalDrive-{#AppVersion}-Windows-x64-Setup
SetupIconFile={#RepoRoot}\assets\game\ui\coastal-drive.ico
UninstallDisplayIcon={app}\coastaldrive.exe
InfoBeforeFile={#RepoRoot}\packaging\development-notice.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式 / Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CoastalDrive (开发试玩版)"; Filename: "{app}\coastaldrive.exe"; WorkingDir: "{app}"
Name: "{group}\车辆实验台"; Filename: "{app}\coastaldrive.exe"; Parameters: "--lab"; WorkingDir: "{app}"
Name: "{group}\下载与使用说明"; Filename: "{app}\README.txt"
Name: "{group}\卸载 CoastalDrive"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CoastalDrive"; Filename: "{app}\coastaldrive.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\coastaldrive.exe"; Description: "启动 CoastalDrive / Launch CoastalDrive"; Flags: nowait postinstall skipifsilent
