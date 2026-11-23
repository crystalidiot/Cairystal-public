"""Hidden native startup without changing global settings or closing user windows."""
import os
import subprocess

def hidden_kwargs():
    if os.name != 'nt':
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {'creationflags': subprocess.CREATE_NO_WINDOW, 'startupinfo': startup}

def visible_window_count(pid):
    """Read-only visibility observation limited to the process started by this job."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    count = 0
    @callback_type
    def visit(window, _):
        nonlocal count
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(window):
            count += 1
        return True
    if not user.EnumWindows(visit, 0):
        return None
    return count
