# ref: https://sjohannes.wordpress.com/tag/win32/

import ctypes
import json
import locale
import os
import re
import subprocess
import sys
import time

stop_sec = None
Win32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))


def open_in_explore(path):
    # filebrowser = os.path.join(os.getenv('WINDIR'), 'explorer.exe')
    path = os.path.normpath(path)
    # cmd = [filebrowser, path] if os.path.isdir(path) else [filebrowser, '/select,', path]
    cmd = f'explorer "{path}"' if os.path.isdir(path) else f'explorer /select, "{path}"'
    os.system(cmd)


def list_pid_and_cmd(name_re='.') -> list:
    default_encoding = locale.getpreferredencoding()
    encoding = 'gbk' if default_encoding == 'cp936' else 'utf-8'
    cmd = 'Get-WmiObject Win32_Process | Select ProcessId,CommandLine | ConvertTo-Json'
    proc = subprocess.run(['powershell', '-Command', cmd], capture_output=True,
                          encoding=default_encoding)
    if proc.returncode != 0:
        return []
    stdout = [(i['ProcessId'], i['CommandLine']) for i in json.loads(proc.stdout)
              if i['ProcessId'] and i['CommandLine']]
    result = [(pid, _cmd) for (pid, _cmd) in stdout if re.search(name_re, _cmd)]
    return result


def activate_window_by_win32(pid):
    def activate_window(hwnd):
        target_pid = ctypes.c_ulong()
        Win32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if pid == target_pid.value:
            # Win32.SendMessageW(hwnd, 0x400, 0x5004, 1)
            Win32.SetForegroundWindow(hwnd)
            Win32.BringWindowToTop(hwnd)
            return True
        else:
            return False

    def each_window(hwnd, _):
        if activate_window(hwnd):
            pass
            # print("Activate: {0}".format(pid))
        return 1

    proc = EnumWindowsProc(each_window)
    Win32.EnumWindows(proc, 0)


def potplayer_time_by_pid(pid):
    def send_message(hwnd):
        global stop_sec
        target_pid = ctypes.c_ulong()
        Win32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if pid == target_pid.value:
            message = Win32.SendMessageW(hwnd, 0x400, 0x5004, 1)
            if message:
                stop_sec = message // 1000

    def for_each_window(hwnd, _):
        send_message(hwnd)
        return True

    proc = EnumWindowsProc(for_each_window)
    Win32.EnumWindows(proc, 0)


def check_process_running(pid):
    is_running = False

    def check_pid_exists(hwnd):
        nonlocal is_running
        target_pid = ctypes.c_ulong()
        Win32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if pid == target_pid.value:
            is_running = True

    def for_each_window(hwnd, _):
        check_pid_exists(hwnd)
        return True

    proc = EnumWindowsProc(for_each_window)
    Win32.EnumWindows(proc, 0)
    return is_running


def get_potplayer_stop_sec(pid=None):
    pid_cmd = list_pid_and_cmd('PotPlayerMini64.exe') if not pid else pid
    if pid_cmd:
        player_pid = pid_cmd[0][0] if not pid else pid
        while True:
            if not check_process_running(player_pid):
                print('pot not running')
                break
            potplayer_time_by_pid(player_pid)
            print(stop_sec)
            time.sleep(0.3)
    return stop_sec


if __name__ == "__main__":
    print(os.de)
