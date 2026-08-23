@echo off
rem ===========================================================================
rem  La Condizione Operaia - rigenerazione del sito
rem
rem    run.bat              rigenera site\testi\ da corpus\it\ e renderizza docs\
rem    run.bat anteprima    rigenera i capitoli e apre l'anteprima ricaricabile
rem    run.bat verifica     controlla soltanto: corpus, allineamento, test
rem
rem  Non modifica mai corpus\it\: la traduzione si scrive solo li'.
rem ===========================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "MODO=%~1"
if "%MODO%"=="" set "MODO=sito"

if /i not "%MODO%"=="sito" if /i not "%MODO%"=="anteprima" if /i not "%MODO%"=="verifica" (
  echo [errore] argomento sconosciuto: %MODO%
  echo Uso: run.bat [anteprima^|verifica]
  exit /b 2
)

rem --- interprete: il virtualenv del progetto se c'e', altrimenti quello di sistema
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
  echo [errore] Python non trovato. Creare l'ambiente con:
  echo     python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -e ".[dev]"
  exit /b 1
)

rem --- accenti corretti nei messaggi degli script
set "PYTHONUTF8=1"

rem --- src\ sul path: gli script funzionano anche senza installazione editable
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

rem --- Quarto serve solo quando si renderizza o si apre l'anteprima
if /i not "%MODO%"=="verifica" (
  set "QUARTO=quarto"
  where quarto >nul 2>&1
  if errorlevel 1 (
    rem Installazione standard per utente: in alcuni ambienti `where` non la
    rem vede anche se la cartella di Quarto compare nel PATH.
    if exist "%LOCALAPPDATA%\Programs\Quarto\bin\quarto.exe" (
      set "QUARTO=%LOCALAPPDATA%\Programs\Quarto\bin\quarto.exe"
    ) else (
      echo [errore] quarto non e' nel PATH. Installarlo da https://quarto.org/docs/get-started/
      exit /b 1
    )
  )
)

if /i "%MODO%"=="verifica" goto :verifica

echo.
echo == genero i capitoli da corpus\it\ ==
"%PYTHON%" scripts\build_site.py
if errorlevel 1 goto :fallito

if /i "%MODO%"=="anteprima" (
  echo.
  echo == anteprima: Ctrl+C per chiudere ==
  call "%QUARTO%" preview site
  if errorlevel 1 goto :fallito
  goto :fine
)

echo.
echo == renderizzo il sito in docs\ (HTML + libro in PDF) ==
call "%QUARTO%" render site
if errorlevel 1 goto :fallito

echo.
echo Fatto. Il sito reso e' in docs\ ^(apri docs\index.html^);
echo il libro in PDF e' docs\la-condizione-operaia.pdf.
echo Per pubblicare: git add corpus/it site/testi docs ^&^& git commit ^&^& git push
goto :fine

:verifica
echo.
echo == validazione del corpus francese ==
"%PYTHON%" scripts\validate_corpus.py
if errorlevel 1 goto :fallito

echo.
echo == site\testi\ allineato a corpus\it\ ==
"%PYTHON%" scripts\build_site.py --check
if errorlevel 1 goto :fallito

echo.
echo == test ==
"%PYTHON%" -m pytest
if errorlevel 1 goto :fallito

echo.
echo Tutti i controlli sono passati.
goto :fine

:fallito
echo.
echo [errore] passaggio fallito ^(codice %errorlevel%^): niente e' stato pubblicato.
exit /b 1

:fine
endlocal
