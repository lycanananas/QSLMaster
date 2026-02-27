[Setup]
AppId={{E7A74B67-8D0D-4A2F-B6F5-1C818E75C184}
AppName=QSLMaster
AppVersion=__VERSION__
AppPublisher=Adrian SQ5FOX Grzeca
AppPublisherURL=https://github.com/lycanananas/QSLMaster
DefaultDirName={autopf}\QSLMaster
DefaultGroupName=QSLMaster
SetupIconFile=qslmaster.ico
UninstallDisplayIcon={app}\qslmaster.exe
LicenseFile=LICENSE.md
OutputDir=dist_installer
OutputBaseFilename=qslmaster-__VERSION__-windows-x86_64-setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons"

[Files]
Source: "dist\qslmaster.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\qslmaster-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\QSLMaster"; Filename: "{app}\qslmaster.exe"
Name: "{group}\QSLMaster CLI"; Filename: "{app}\qslmaster-cli.exe"
Name: "{autodesktop}\QSLMaster"; Filename: "{app}\qslmaster.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\qslmaster.exe"; Description: "Launch QSLMaster"; Flags: nowait postinstall skipifsilent
