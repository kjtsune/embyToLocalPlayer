# ref: https://sjohannes.wordpress.com/tag/win32/

import ctypes
import json
import re
import subprocess

from utils.configs import MyLogger

logger = MyLogger()
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))


def list_pid_and_cmd(name_re: str = '.') -> list:
    cmd = 'Get-WmiObject Win32_Process | Select-Object ProcessId, CommandLine | ConvertTo-Json'
    name_re = re.compile(name_re)
    try:
        proc = subprocess.run(['chcp', '65001', '>', 'NUL', '&', 'powershell', cmd],
                              capture_output=True, encoding='utf-8-sig', shell=True)
    except FileNotFoundError:
        raise FileNotFoundError('powershell not found in cmd, check sys and user environment path') from None
    if proc.returncode != 0:
        return []
    stdout = proc.stdout
    try:
        stdout = json.loads(stdout)
    except Exception:
        logger.error(f'{stdout=}')
        logger.error('powershell stdout error, kill python by yourself in task manager if you need to restart script')
        return []
    result = [(i['ProcessId'], i['CommandLine']) for i in stdout
              if i['ProcessId'] and i['CommandLine'] and name_re.search(i['CommandLine'])]
    return result


class RECT(ctypes.Structure):
    _fields_ = [
        ('left', ctypes.c_long),
        ('top', ctypes.c_long),
        ('right', ctypes.c_long),
        ('bottom', ctypes.c_long),
    ]


def activate_window_by_win32(pid):
    max_size = 0
    max_size_hwnd = None

    def activate_window(hwnd):
        nonlocal max_size
        nonlocal max_size_hwnd
        target_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        # 注意一个进程可能有多个窗口，要过滤出最合适的那个窗口
        if pid == target_pid.value:
            # 排除掉不可见窗口
            visible = user32.IsWindowVisible(hwnd)
            if not visible:
                return False
            # 排除掉标题为空的窗口
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return False

            # buff = ctypes.create_unicode_buffer(length + 1)
            # user32.GetWindowTextW(hwnd, buff, length + 1)
            # print(f'title: {buff.value}')

            # 以上两个过滤，已经可以通过mpv mpc-be mpc-hc vlc potplayer播放器的测试了
            # 为兼容更多其他播放器 剩余窗口中保留最大那个窗口
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            # print(f'left: {rect.left}, right: {rect.right}, top: {rect.top}, bottom: {rect.bottom}')
            if (rect.right - rect.left) * (rect.bottom - rect.top) <= max_size:
                return False
            max_size = (rect.right - rect.left) * (rect.bottom - rect.top)
            max_size_hwnd = hwnd
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

    if max_size_hwnd is not None:
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
        foreground_hwnd = user32.GetForegroundWindow()
        # 当前激活窗口的pid
        remote_pid = user32.GetWindowThreadProcessId(foreground_hwnd, 0)
        # 关键点
        # https://learn.microsoft.com/zh-cn/windows/win32/api/winuser/nf-winuser-attachthreadinput
        # 一个线程的输入处理机制附加到另一个线程，两个线程共享输入状态
        # 满足4.调用进程收到了最后一个输入事件
        user32.AttachThreadInput(curr_pid, remote_pid, True)
        user32.SetForegroundWindow(max_size_hwnd)
        user32.BringWindowToTop(max_size_hwnd)
        # 分离两个线程
        user32.AttachThreadInput(curr_pid, remote_pid, False)
        return True


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
                logger.trace(f'{title=} {pid=}')
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
