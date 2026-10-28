#ifndef PayloadDir
  #error PayloadDir must point to the staged application
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
[Setup]
AppId={{E66D7E5E-9928-4B46-B062-EF50F7B84341}
AppName=JARVIS OS
AppVersion=0.10.4
AppPublisher=JARVIS OS
DefaultDirName={localappdata}\Programs\JARVIS OS
DefaultGroupName=JARVIS OS
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=JARVIS-OS-0.10.4-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=JARVIS OS
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "Utwórz skrót na pulpicie"; Flags: checkedonce

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JARVIS OS"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I ""{app}\app\scripts\windows_launcher.py"""; WorkingDir: "{app}\app"
Name: "{autodesktop}\JARVIS OS"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I ""{app}\app\scripts\windows_launcher.py"""; WorkingDir: "{app}\app"; Tasks: desktopicon
Name: "{group}\Odinstaluj JARVIS OS"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I ""{app}\app\scripts\windows_launcher.py"""; Description: "Uruchom JARVIS OS"; Flags: nowait postinstall skipifsilent

; User data lives outside {app}; uninstall deliberately preserves it.
