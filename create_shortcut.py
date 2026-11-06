import os
import sys
import subprocess

def create_desktop_shortcut():
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    shortcut_path = os.path.join(desktop, 'Campus Bus Tracker.lnk')
    
    # Target batch file in root workspace or subfolder
    root_bat = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Run Bus Tracker.bat'))
    sub_bat = os.path.abspath(os.path.join(os.path.dirname(__file__), 'run.bat'))
    target_bat = root_bat if os.path.exists(root_bat) else sub_bat
        
    work_dir = os.path.abspath(os.path.dirname(__file__))
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'bus_icon.ico'))
    
    vbs_script = f'''
Set WshShell = CreateObject("WScript.Shell")
Set oLink = WshShell.CreateShortcut("{shortcut_path}")
oLink.TargetPath = "{target_bat}"
oLink.WorkingDirectory = "{work_dir}"
oLink.IconLocation = "{icon_path},0"
oLink.Description = "Launch Campus Bus Tracker"
oLink.WindowStyle = 1
oLink.Save
'''
    temp_vbs = os.path.join(os.path.dirname(__file__), '_temp_shortcut.vbs')
    try:
        with open(temp_vbs, 'w', encoding='utf-8') as f:
            f.write(vbs_script)
        subprocess.run(['cscript', '//nologo', temp_vbs], check=True, capture_output=True)
        print(f"[OK] Desktop shortcut created successfully!")
        print(f"     Path: {shortcut_path}")
        return True
    except Exception as e:
        print(f"[!] Could not create shortcut: {e}")
        return False
    finally:
        if os.path.exists(temp_vbs):
            try:
                os.remove(temp_vbs)
            except OSError:
                pass

if __name__ == '__main__':
    create_desktop_shortcut()
