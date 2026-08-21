@echo off
setlocal

rem Подготовка каталога Newfon_core к выкладке в отдельный репозиторий.
rem Скрипт только готовит всё локально, push не делает: команду для него
rem он напечатает в конце.

set "ROOT=%~dp0"
set "CORE=%ROOT%Newfon_core"
set "URL=https://github.com/nikkov199525/Newfon_core"

where git.exe >nul 2>&1
if errorlevel 1 (
	echo Не найден git. Установить: winget install Git.Git
	exit /b 1
)

if not exist "%CORE%\src\voices.c" (
	echo Не найден каталог ядра: %CORE%
	exit /b 1
)

pushd "%CORE%"

if exist ".git" (
	echo Репозиторий в Newfon_core уже есть.
) else (
	git init -b main
	if errorlevel 1 goto :fail
	echo Создан репозиторий в Newfon_core.
)

git add -A
if errorlevel 1 goto :fail

for /f %%N in ('git diff --cached --name-only ^| find /c /v ""') do echo Будет зафиксировано файлов: %%N

git diff --cached --quiet
if errorlevel 1 (
	rem Сообщение по-английски: батник в кодировке консоли,
	rem и кириллица попала бы в историю в неверной кодировке
	git commit -m "Newfon speech core built from ru_tts sources"
	if errorlevel 1 goto :fail
	echo Изменения зафиксированы.
) else (
	echo Фиксировать нечего, изменений нет.
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
	git remote add origin "%URL%"
	if errorlevel 1 goto :fail
	echo Добавлен origin: %URL%
) else (
	for /f "usebackq tokens=*" %%U in (`git remote get-url origin`) do echo Origin уже задан: %%U
)

popd
echo.
echo Ядро готово. Создайте на GitHub пустой репозиторий Newfon_core
echo без файлов README и лицензии, после чего выполните:
echo.
echo     git -C "%CORE%" push -u origin main
echo.
echo Когда ядро окажется на GitHub, запускайте git-addon-init.bat.
exit /b 0

:fail
set "RC=%ERRORLEVEL%"
popd
echo.
echo Не получилось, код %RC%.
exit /b %RC%
