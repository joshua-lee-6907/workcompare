; Inno Setup portable sandbox wrapper
[Setup]
AppName=ILRT App
AppVersion=1.0.0
DefaultDirName={autopf}\ILRT-App
DefaultGroupName=ILRT-App
OutputBaseFilename=ILRT-App-Portable
Compression=lzma
SolidCompression=yes
DisableDirPage=no
DisableProgramGroupPage=yes
Uninstallable=no

[Files]
Source: "..\dist\ILRT-App\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\ILRT App"; Filename: "{app}\ILRT-App.exe"

[Run]
Filename: "{app}\ILRT-App.exe"; Description: "Launch ILRT App"; Flags: nowait postinstall skipifsilent
