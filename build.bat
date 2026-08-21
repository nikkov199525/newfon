@echo off
setlocal enabledelayedexpansion

rem Сборка дополнения Newfon.
rem
rem   build.bat            собрать newfon.nvda-addon
rem   build.bat clean      удалить результаты сборки
rem   build.bat clean-all  то же плюс собранные зависимости (pcre2)
rem   build.bat pot        обновить шаблон перевода
rem   build.bat deps       доустановить модуль markdown для Python

set "ROOT=%~dp0"
set "TARGET=%*"
if "%TARGET%"=="" set "TARGET=all"

echo Сборка дополнения Newfon, цель: %TARGET%
echo.

rem ---------------------------------------------------------------- Git
rem Из состава Git for Windows нужны sh, mkdir, rm, touch: на них опирается Makefile
where sh.exe >nul 2>&1
if errorlevel 1 (
	for %%D in ("%ProgramFiles%\Git" "%ProgramFiles(x86)%\Git" "%LOCALAPPDATA%\Programs\Git") do (
		if exist "%%~D\usr\bin\sh.exe" set "PATH=%%~D\usr\bin;!PATH!"
	)
)
where sh.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден Git for Windows.
	echo Нужны sh, mkdir, rm и touch из его состава: https://git-scm.com/download/win
	exit /b 1
)

rem --------------------------------------------------------- llvm-mingw
where i686-w64-mingw32-clang.exe >nul 2>&1
if errorlevel 1 (
	set "LLVM="
	for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\MartinStorsjo.LLVM-MinGW*") do (
		for /d %%E in ("%%~fD\llvm-mingw-*") do (
			if exist "%%~fE\bin\i686-w64-mingw32-clang.exe" set "LLVM=%%~fE\bin"
		)
	)
	if not defined LLVM (
		for %%D in ("C:\llvm-mingw" "%ProgramFiles%\llvm-mingw" "%LOCALAPPDATA%\Programs\llvm-mingw") do (
			if exist "%%~D\bin\i686-w64-mingw32-clang.exe" set "LLVM=%%~D\bin"
		)
	)
	if defined LLVM set "PATH=!LLVM!;!PATH!"
)
where i686-w64-mingw32-clang.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден llvm-mingw с целями i686-w64-mingw32 и x86_64-w64-mingw32.
	echo Установить: winget install MartinStorsjo.LLVM-MinGW.UCRT
	exit /b 1
)
where x86_64-w64-mingw32-clang.exe >nul 2>&1
if errorlevel 1 (
	echo В найденном llvm-mingw нет цели x86_64-w64-mingw32, нужна сборка ucrt-x86_64.
	exit /b 1
)
where mingw32-make.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден mingw32-make, он входит в состав llvm-mingw.
	exit /b 1
)

rem -------------------------------------------------------------- CMake
where cmake.exe >nul 2>&1
if errorlevel 1 (
	for %%D in ("%ProgramFiles%\CMake\bin" "%ProgramFiles(x86)%\CMake\bin") do (
		if exist "%%~D\cmake.exe" set "PATH=%%~D;!PATH!"
	)
)
where cmake.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден CMake, он нужен для сборки pcre2.
	echo Установить: winget install Kitware.CMake
	exit /b 1
)

rem -------------------------------------------------------------- 7-Zip
where 7z.exe >nul 2>&1
if errorlevel 1 (
	for %%D in ("%ProgramFiles%\7-Zip" "%ProgramFiles(x86)%\7-Zip" "%LOCALAPPDATA%\Programs\7-Zip") do (
		if exist "%%~D\7z.exe" set "PATH=%%~D;!PATH!"
	)
)
where 7z.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден 7-Zip, он упаковывает готовое дополнение.
	echo Установить: winget install 7zip.7zip
	exit /b 1
)

rem ------------------------------------------------------------- Python
where python.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден Python 3, он собирает документацию и каталоги переводов.
	echo Установить: winget install Python.Python.3.12
	exit /b 1
)

if /i "%TARGET%"=="deps" (
	echo Установка модуля markdown...
	python -m pip install markdown
	exit /b !ERRORLEVEL!
)

python -c "import markdown" >nul 2>&1
if errorlevel 1 (
	echo Для Python не установлен модуль markdown, он собирает документацию.
	echo Установить: build.bat deps
	exit /b 1
)

rem --------------------------------------------------------------- Сборка
pushd "%ROOT%src"
mingw32-make %TARGET%
set "RC=%ERRORLEVEL%"
popd

echo.
if not "%RC%"=="0" (
	echo Сборка завершилась с ошибкой, код %RC%.
	exit /b %RC%
)

if exist "%ROOT%src\newfon.nvda-addon" (
	for %%F in ("%ROOT%src\newfon.nvda-addon") do echo Готово: %%~fF, %%~zF байт
) else (
	echo Готово.
)
exit /b 0
