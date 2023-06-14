# ref: https://sjohannes.wordpress.com/tag/win32/

import ctypes
import json
import locale
import re
import subprocess

from utils.configs import MyLogger

logger = MyLogger()
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))


def list_pid_and_cmd(name_re='.') -> list:
    default_encoding = locale.getpreferredencoding()
    # encoding = 'gbk' if default_encoding == 'cp936' else 'utf-8'
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
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if pid == target_pid.value:
            # SetForegroundWindow激活窗口至少满足以下条件之一
            # https://learn.microsoft.com/zh-cn/windows/win32/api/winuser/nf-winuser-setforegroundwindow
            # 1.调用进程是前台进程。
            # 2.调用进程由前台进程启动。
            # 3.当前没有前台窗口，因此没有前台进程。
            # 4.调用进程收到了最后一个输入事件。
            # 5.正在调试前台进程或调用进程。
            
            # 要一些特殊的操作来实现
            
            # 当前线程pid，即当前python程序的线程，是播放器进程的调用者
            curr_pid = kernel32.GetCurrentThreadId()
            # 当前激活的窗口
            foregroundHwnd = user32.GetForegroundWindow()
            # 当前激活窗口的pid
            remote_pid = user32.GetWindowThreadProcessId(foregroundHwnd, 0)
            # 关键点
            # https://learn.microsoft.com/zh-cn/windows/win32/api/winuser/nf-winuser-attachthreadinput
            # 一个线程的输入处理机制附加到另一个线程，两个线程共享输入状态
            # 满足4.调用进程收到了最后一个输入事件
            user32.AttachThreadInput(curr_pid, remote_pid, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            # 分离两个线程
            user32.AttachThreadInput(curr_pid, remote_pid, False)
            return True
        else:
            return False

    def each_window(hwnd, _):
        if activate_window(hwnd):
            pass
            # print("Activate: {0}".format(pid))
        return 1

    proc = EnumWindowsProc(each_window)
    user32.EnumWindows(proc, 0)


def process_is_running_by_pid(pid):
    is_running = False

    def check_pid_exists(hwnd):
        nonlocal is_running
        target_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if pid == target_pid.value:
            is_running = True

    def for_each_window(hwnd, _):
        check_pid_exists(hwnd)
        return True

    proc = EnumWindowsProc(for_each_window)
    user32.EnumWindows(proc, 0)
    return is_running


def find_pid_by_windows_title(title):
    pid = None

    def for_each_window(hwnd, _):
        nonlocal pid
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            if title in buff.value:
                target_pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
                pid = target_pid.value
                logger.debug(f'{title=} {pid=}')
        return True

    proc = EnumWindowsProc(for_each_window)
    user32.EnumWindows(proc, 0)
    return pid


def find_pid_by_process_name(name=None, name_re=None):
    pid = None if not name_re else []

    def for_each_window(hwnd, _):
        nonlocal pid
        process_name = get_window_thread_process_name(hwnd)
        if (not name_re and name in process_name) or (not name and re.search(name_re, process_name, re.I)):
            target_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
            pid_value = target_pid.value
            if name:
                pid = pid_value
            else:
                pid.append(pid_value)
            # print(process_name, pid_value)
        return True

    proc = EnumWindowsProc(for_each_window)
    user32.EnumWindows(proc, 0)
    return pid


def get_window_thread_process_name(hwnd):
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.pointer(pid))
    handle = kernel32.OpenProcess(0x0410, 0, pid)
    buffer_len = ctypes.c_ulong(1024)
    buffer = ctypes.create_unicode_buffer(buffer_len.value)
    kernel32.QueryFullProcessImageNameW(handle, 0, ctypes.pointer(buffer), ctypes.pointer(buffer_len))
    buffer = buffer[:]
    buffer = buffer[:buffer.index('\0')]
    return str(buffer)
