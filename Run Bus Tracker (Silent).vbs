Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)

If fso.FileExists(strDir & "\server.py") Then
    targetDir = strDir
Else
    targetDir = strDir & "\BusTracker"
End If

WshShell.CurrentDirectory = targetDir
WshShell.Run "pythonw server.py", 0, False
