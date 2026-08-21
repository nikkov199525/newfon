@echo off
setlocal enabledelayedexpansion

rem Фиксация изменений и выкладка их в форк дополнения.
rem Скрипт по порядку:
rem   1) убеждается, что ядро и зависимости подключены именно подмодулями;
rem   2) фиксирует и отправляет изменения ядра в его репозиторий, иначе
rem      указатель на ядро в дополнении будет вести в никуда;
rem   3) фиксирует изменения дополнения вместе с новыми указателями
rem      подмодулей и отправляет их в форк.
rem
rem   git-addon-push.bat                     коммит и push в ветку main
rem   git-addon-push.bat "текст коммита"     то же со своим сообщением
rem   git-addon-push.bat /master ["текст"]   отправить в master форка, заменив её
rem   git-addon-push.bat /y ...              ничего не спрашивать

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "ASSUME_YES="
set "TO_MASTER="
set "MSG="

:parse
if "%~1"=="" goto :parsed
if /i "%~1"=="/y" (
	set "ASSUME_YES=1"
	shift
	goto :parse
)
if /i "%~1"=="/master" (
	set "TO_MASTER=1"
	shift
	goto :parse
)
set "MSG=%~1"
shift
goto :parse
:parsed
if not defined MSG set "MSG=Update addon"

where git.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден git. Установить: winget install Git.Git
	exit /b 1
)

if not exist "src\Makefile" (
	echo Скрипт нужно запускать из каталога проекта.
	exit /b 1
)

if not exist ".git" (
	echo Здесь ещё нет репозитория. Сначала выполните git-addon-init.bat
	exit /b 1
)

set "ORIGIN="
for /f "usebackq tokens=*" %%U in (`git remote get-url origin 2^>nul`) do set "ORIGIN=%%U"
if not defined ORIGIN (
	echo Не задан origin. Сначала выполните git-addon-init.bat
	exit /b 1
)

set "BRANCH="
for /f "usebackq tokens=*" %%B in (`git rev-parse --abbrev-ref HEAD`) do set "BRANCH=%%B"
if not defined BRANCH goto :fail

echo Дополнение: !ORIGIN!
echo Ветка: !BRANCH!
echo Сообщение коммита: !MSG!
echo.

echo Проверяю подмодули...
set "BROKEN="
call :checksub "Newfon_core"
call :checksub "external/rulex"
call :checksub "external/lmdb"
call :checksub "external/pcre2"
call :checksub "external/libsamplerate"
if defined BROKEN (
	echo.
	echo Ядро и зависимости должны подключаться подмодулями, а не лежать
	echo в репозитории файлами. Исправляет это git-addon-init.bat
	exit /b 1
)
echo.

set "CORE_DIRTY="
for /f "usebackq tokens=*" %%L in (`git -C Newfon_core status --porcelain`) do set "CORE_DIRTY=1"
if defined CORE_DIRTY (
	echo В ядре есть незафиксированные изменения:
	git -C Newfon_core status --short
	call :ask "Зафиксировать их в репозитории ядра?"
	if errorlevel 1 (
		echo Пропускаю ядро, в форк его изменения не попадут.
	) else (
		git -C Newfon_core add -A
		if errorlevel 1 goto :fail
		call :commit "Newfon_core"
		if errorlevel 1 goto :fail
		echo Изменения ядра зафиксированы.
	)
	echo.
)

set "CORE_BRANCH="
for /f "usebackq tokens=*" %%B in (`git -C Newfon_core rev-parse --abbrev-ref HEAD`) do set "CORE_BRANCH=%%B"
set "CORE_ORIGIN="
for /f "usebackq tokens=*" %%U in (`git -C Newfon_core remote get-url origin 2^>nul`) do set "CORE_ORIGIN=%%U"
if not defined CORE_ORIGIN (
	echo У ядра не задан origin, отправлять его некуда.
	echo Поможет git-core-init.bat
	exit /b 1
)

git -C Newfon_core fetch --quiet origin
set "AHEAD=0"
git -C Newfon_core rev-parse --verify --quiet "origin/!CORE_BRANCH!" >nul
if errorlevel 1 (
	set "AHEAD=new"
) else (
	for /f %%N in ('git -C Newfon_core rev-list --count origin/!CORE_BRANCH!..!CORE_BRANCH! 2^>nul') do set "AHEAD=%%N"
)
if not "!AHEAD!"=="0" (
	echo Ядро отличается от выложенного, а указатель на невыложенный
	echo коммит сделает подмодуль нерабочим.
	call :ask "Отправить ядро в !CORE_ORIGIN!?"
	if errorlevel 1 (
		echo Отменено, ничего не отправлено.
		exit /b 1
	)
	git -C Newfon_core push -u origin !CORE_BRANCH!
	if errorlevel 1 goto :fail
	echo Ядро отправлено.
	echo.
)

git add -A
if errorlevel 1 goto :fail

git diff --cached --quiet
if errorlevel 1 (
	echo Будет зафиксировано:
	git status --short
	for /f %%N in ('git diff --cached --name-only ^| find /c /v ""') do echo Файлов: %%N
	call :ask "Фиксируем?"
	if errorlevel 1 (
		echo Отменено, коммит не сделан.
		exit /b 1
	)
	call :commit "."
	if errorlevel 1 goto :fail
	echo Зафиксировано.
) else (
	echo Новых изменений нет, отправляю то, что уже зафиксировано.
)
echo.

if defined TO_MASTER (
	echo Ветка master в форке будет заменена содержимым ветки !BRANCH!,
	echo а прежняя история newfon останется только в старых коммитах.
	call :ask "Точно заменяем master?"
	if errorlevel 1 (
		echo Отменено. Всё зафиксировано локально.
		exit /b 1
	)
	git push --force origin !BRANCH!:master
	if errorlevel 1 goto :pushfail
	echo Отправлено в master.
) else (
	call :ask "Отправить ветку !BRANCH! в !ORIGIN!?"
	if errorlevel 1 (
		echo Отменено. Всё зафиксировано локально, отправить потом:
		echo     git push -u origin !BRANCH!
		exit /b 1
	)
	git push -u origin !BRANCH!
	if errorlevel 1 goto :pushfail
	echo Отправлено.
)
exit /b 0

rem ------------------------------------------------ проверка подмодуля
:checksub
rem Права 160000 в индексе бывают только у подмодуля: git submodule status
rem возвращает ноль и для обычного каталога, на него полагаться нельзя
git ls-files --stage -- "%~1" | findstr /b /c:"160000 " >nul
if errorlevel 1 (
	echo   %~1: лежит в репозитории файлами, а не подмодулем
	set "BROKEN=1"
	exit /b 0
)
if not exist "%~1\.git" (
	echo   %~1: не выгружен, выгружаю
	git submodule update --init --recursive -- "%~1"
	if errorlevel 1 (
		set "BROKEN=1"
		exit /b 0
	)
)
echo   %~1 - подмодуль
exit /b 0

rem -------------------------------------------------------- коммит
:commit
rem Сообщение пишется во временный файл в UTF-8: иначе кириллица уйдёт
rem в историю в кодировке консоли и превратится в кракозябры
set "MSGFILE=%TEMP%\newfon-commit-msg.txt"
del "%MSGFILE%" >nul 2>&1
powershell -NoProfile -Command "[IO.File]::WriteAllText($env:MSGFILE, $env:MSG + [char]10, (New-Object Text.UTF8Encoding $false))" >nul 2>&1
if exist "%MSGFILE%" (
	git -C "%~1" commit -q -F "%MSGFILE%"
	set "RC=!ERRORLEVEL!"
	del "%MSGFILE%" >nul 2>&1
	exit /b !RC!
)
git -C "%~1" commit -q -m "%MSG%"
exit /b %ERRORLEVEL%

rem --------------------------------------------------------- вопрос
:ask
if defined ASSUME_YES exit /b 0
set "ANSWER="
set /p "ANSWER=%~1 [y/n] "
if /i "!ANSWER!"=="y" exit /b 0
exit /b 1

:pushfail
echo.
echo Отправить не удалось. Чаще всего это значит, что в форке есть коммиты,
echo которых нет здесь. Посмотреть, что там: git fetch origin
echo Если ветку в форке нужно заменить своей: git-addon-push.bat /master
echo Всё зафиксированное никуда не делось, оно лежит локально.
exit /b 1

:fail
set "RC=%ERRORLEVEL%"
echo.
echo Не получилось, код %RC%.
exit /b %RC%
