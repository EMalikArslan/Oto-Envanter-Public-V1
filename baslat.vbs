Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\AresEnvanter"
sh.Run """C:\Users\USER\AppData\Local\Programs\Python\Python311\pythonw.exe"" ""C:\AresEnvanter\main.py""", 0, False
