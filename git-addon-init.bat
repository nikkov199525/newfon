@echo off
setlocal enabledelayedexpansion

rem Подготовка этого каталога к выкладке в форк дополнения.
rem Ядро и внешние зависимости подключаются подмодулями, адреса те же,
rem что перечислены в .gitmodules. Локальные копии зависимостей при этом
rem заменяются клонами, поэтому нужен интернет.
rem
rem Скрипт только готовит всё локально, push не делает: команду для него
rem он напечатает в конце.
rem
rem   git-addon-init.bat        спросить подтверждение и подключить подмодули
rem   git-addon-init.bat /y     то же без вопросов

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "ADDON_URL=https://github.com/nikkov199525/newfon"
set "CORE_URL=https://github.com/nikkov199525/Newfon_core"

where git.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден git. Установить: winget install Git.Git
	exit /b 1
)

if not exist "src\Makefile" (
	echo Скрипт нужно запускать из каталога проекта.
	exit /b 1
)

echo Проверяю доступность репозиториев...
call :check "ядро"          "%CORE_URL%"                                  || exit /b 1
call :check "rulex"         "https://github.com/poretsky/rulex"           || exit /b 1
call :check "lmdb"          "https://github.com/LMDB/lmdb"                || exit /b 1
call :check "pcre2"         "https://github.com/PCRE2Project/pcre2"       || exit /b 1
call :check "libsamplerate" "https://github.com/nikkov199525/libsamplerate" || exit /b 1
echo Все репозитории доступны.
echo.

if /i "%~1"=="/y" goto :confirmed
echo Локальные копии каталогов Newfon_core и external будут заменены клонами.
echo Всё, что в них не выложено на GitHub, пропадёт.
set "ANSWER="
set /p "ANSWER=Продолжать? [y/n] "
if /i not "!ANSWER!"=="y" (
	echo Отменено, ничего не тронуто.
	exit /b 1
)
:confirmed

if exist ".git" (
	echo Репозиторий уже есть.
) else (
	git init -b main
	if errorlevel 1 goto :fail
	echo Создан репозиторий.
)

call :add "Newfon_core"           "%CORE_URL%"                                  || goto :fail
call :add "external/rulex"        "https://github.com/poretsky/rulex"           || goto :fail
call :add "external/lmdb"         "https://github.com/LMDB/lmdb"                || goto :fail
call :add "external/pcre2"        "https://github.com/PCRE2Project/pcre2"       || goto :fail
call :add "external/libsamplerate" "https://github.com/nikkov199525/libsamplerate" || goto :fail

echo Догружаю вложенные подмодули...
git submodule update --init --recursive
if errorlevel 1 goto :fail

git add -A
if errorlevel 1 goto :fail

for /f %%N in ('git diff --cached --name-only ^| find /c /v ""') do echo Будет зафиксировано файлов: %%N

git diff --cached --quiet
if errorlevel 1 (
	rem Сообщение по-английски: батник в кодировке консоли,
	rem и кириллица попала бы в историю в неверной кодировке
	git commit -m "Newfon on the new core: core and dependencies as submodules"
	if errorlevel 1 goto :fail
	echo Изменения зафиксированы.
) else (
	echo Фиксировать нечего, изменений нет.
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
	git remote add origin "%ADDON_URL%"
	if errorlevel 1 goto :fail
	echo Добавлен origin: %ADDON_URL%
) else (
	for /f "usebackq tokens=*" %%U in (`git remote get-url origin`) do echo Origin уже задан: %%U
)

echo.
echo Проверьте, что всё собирается из подмодулей:
echo.
echo     build.bat
echo.
echo В форке лежит старое дополнение, его ветка называется master,
echo и эта история её не продолжает. Выложить новой веткой, ничего
echo не ломая, а потом при желании сделать её основной в настройках
echo репозитория:
echo.
echo     git push -u origin main
echo.
echo Либо сразу заменить содержимое master в форке:
echo.
echo     git push --force origin main:master
exit /b 0

rem ------------------------------------------------------------- проверка
:check
git ls-remote --exit-code "%~2" >nul 2>&1
if errorlevel 1 (
	echo   недоступен или пуст: %~2
	echo   Это %~1. Если речь о ядре, сначала создайте репозиторий на GitHub,
	echo   выполните git-core-init.bat и отправьте ядро командой push.
	exit /b 1
)
echo   доступен: %~2
exit /b 0

rem ----------------------------------------------------- добавить подмодуль
:add
rem Проверка именно на подмодуль: git submodule status возвращает ноль
rem и для обычного каталога, поэтому смотрим права 160000 в индексе
git ls-files --stage -- "%~1" | findstr /b /c:"160000 " >nul
if not errorlevel 1 (
	echo   %~1 уже подключён
	exit /b 0
)
git ls-files --error-unmatch -- "%~1" >nul 2>&1
if not errorlevel 1 (
	echo   %~1 лежит в репозитории обычными файлами, убираю из индекса
	git rm -r --cached --quiet -- "%~1"
	if errorlevel 1 exit /b 1
)
if exist "%~1" (
	echo   заменяю локальную копию %~1
	rmdir /s /q "%~1"
	if exist "%~1" (
		echo   не удалось удалить %~1
		exit /b 1
	)
)
git submodule add --force "%~2" "%~1"
if errorlevel 1 exit /b 1
echo   подключён %~1
exit /b 0

:fail
set "RC=%ERRORLEVEL%"
echo.
echo Не получилось, код %RC%.
exit /b %RC%
