@echo off
setlocal
cd /d "%~dp0"
if not exist "assets\default.xbe" (
 echo Supply your extracted Xbox game in assets first. See START-HERE.txt.
 exit /b 1
)
where clang++ >nul 2>&1
if errorlevel 1 (
 echo Run from an x64 Visual Studio developer prompt with LLVM, CMake and Ninja on PATH.
 exit /b 1
)
cmake --preset release
if errorlevel 1 exit /b 1
cmake --build --preset release --target MVP05 --parallel 4
if errorlevel 1 exit /b 1
copy /y "out\build\release\MVP05.exe" "MVP05.exe" >nul
if errorlevel 1 exit /b 1
rem Microsoft's shader compiler beside the exe under its own name, which the game loads first: under Proton
rem (SteamOS) the system's d3dcompiler_47 is Wine's, which can't compile the game's shaders (a black screen)
set "D3DC="
if defined WindowsSdkDir if exist "%WindowsSdkDir%Redist\D3D\x64\d3dcompiler_47.dll" set "D3DC=%WindowsSdkDir%Redist\D3D\x64\d3dcompiler_47.dll"
if not defined D3DC if exist "%ProgramFiles(x86)%\Windows Kits\10\Redist\D3D\x64\d3dcompiler_47.dll" set "D3DC=%ProgramFiles(x86)%\Windows Kits\10\Redist\D3D\x64\d3dcompiler_47.dll"
if not defined D3DC if exist "%SystemRoot%\System32\d3dcompiler_47.dll" set "D3DC=%SystemRoot%\System32\d3dcompiler_47.dll"
if defined D3DC copy /y "%D3DC%" "d3dcompiler_ms.dll" >nul
if not defined D3DC echo No d3dcompiler_47.dll found to copy: under Proton, copy one beside the exe as d3dcompiler_ms.dll.
echo Built MVP05.exe beside assets. No game was launched.
