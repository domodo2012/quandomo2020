@echo off
title Oracle�������
cls
rem color 2f
goto MENU

:MENU
cls
echo. =-=-=-=-=Oracle�������=-=-=-=-=
echo.
echo. 1 ��������
echo.
echo. 2 �رշ���
echo.
echo. 3 �� ��
echo.
echo. =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

echo. ������ѡ����Ŀ����ţ�
set /p ID=
if "%id%"=="1" goto cmd1
if "%id%"=="2" goto cmd2
if "%id%"=="3" exit

echo ��������ȷ���!&ping -n 2 127.1>nul&goto MENU

:cmd1
echo.
echo ����Oracle������...
rem net start|findstr /i /c:"Oracle ORCL VSS Writer Service">nul&&set k=1||set k=0
rem if %k%==0 (net start "Oracle ORCL VSS Writer Service")
net start|findstr /i /c:"OracleDBConsoleorcl">nul&&set k=1||set k=0
if %k%==0 (net start "OracleDBConsoleorcl")
rem net start|findstr /i /c:"OracleJobSchedulerORCL">nul&&set k=1||set k=0
rem if %k%==0 (net start "OracleJobSchedulerORCL")
rem net start|findstr /i /c:"OracleMTSRecoveryService">nul&&set k=1||set k=0
rem if %k%==0 (net start "OracleMTSRecoveryService")
rem net start|findstr /i /c:"OracleOraDb11g_home1ClrAgent">nul&&set k=1||set k=0
rem if %k%==0 (net start "OracleOraDb11g_home1ClrAgent")
net start|findstr /i /c:"OracleOraDb11g_home1TNSListener">nul&&set k=1||set k=0
if %k%==0 (net start "OracleOraDb11g_home1TNSListener")
net start|findstr /i /c:"OracleServiceORCL">nul&&set k=1||set k=0
if %k%==0 (net start "OracleServiceORCL")

echo.
echo Oracle�����Ѿ��ɹ�����...
echo.
pause
goto MENU

:cmd2
echo.
echo �ر�Oracle������...
net start|findstr /i /c:"Oracle ORCL VSS Writer Service">nul&&set k=1||set k=0
if %k%==1 (net stop "Oracle ORCL VSS Writer Service")
net start|findstr /i /c:"OracleDBConsoleorcl">nul&&set k=1||set k=0
if %k%==1 (net stop "OracleDBConsoleorcl")
net start|findstr /i /c:"OracleJobSchedulerORCL">nul&&set k=1||set k=0
if %k%==1 (net stop "OracleJobSchedulerORCL")
net start|findstr /i /c:"OracleMTSRecoveryService">nul&&set k=1||set k=0
if %k%==1 (net stop "OracleMTSRecoveryService")
net start|findstr /i /c:"OracleOraDb11g_home1ClrAgent">nul&&set k=1||set k=0
if %k%==1 (net stop "OracleOraDb11g_home1ClrAgent")
net start|findstr /i /c:"OracleOraDb11g_home1TNSListener">nul&&set k=1||set k=0
if %k%==1 (net stop "OracleOraDb11g_home1TNSListener")
net start|findstr /i /c:"OracleServiceORCL">nul&&set k=1||set k=0
if %k%==1 (net stop "OracleServiceORCL")

echo.
echo Oracle�����Ѿ��ɹ��ر�...
echo.
pause
goto MENU