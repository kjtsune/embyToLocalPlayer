import json
import os.path
import os.path
import platform
import signal
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from utils.configs import configs, MyLogger
from utils.python_mpv_jsonipc import MPV
from utils.tools import activate_window_by_pid, check_stop_sec, requests_urllib

logger = MyLogger()


def start_mpv_player(cmd, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    is_darwin = True if platform.system() == 'Darwin' else False
    is_iina = True if 'iina-cli' in cmd[0] else False
    _t = str(time.time())
    pipe_name = 'embyToMpv' + chr(98 + int(_t[-1])) + chr(98 + int(_t[-2]))
    # pipe_name = 'embyToMpv'
    cmd_pipe = fr'\\.\pipe\{pipe_name}' if os.name == 'nt' else f'/tmp/{pipe_name}.pipe'
    pipe_name = pipe_name if os.name == 'nt' else cmd_pipe
    # cmd.append(f'--http-proxy=http://127.0.0.1:7890')
    if sub_file:
        cmd.append(f'--sub-file={sub_file}')
    if media_title:
        cmd.append(f'--force-media-title={media_title}')
        cmd.append(f'--osd-playing-msg={media_title}')
    else:
        cmd.append('--osd-playing-msg=${path}')
    if start_sec is not None:
        cmd.append(f'--start={start_sec}')
    if is_darwin:
        cmd.append('--focus-on-open')
    cmd.append(fr'--input-ipc-server={cmd_pipe}')
    # cmd.append('--fullscreen')
    if configs.disable_audio:
        cmd.append('--no-audio')
        # cmd.append('--no-video')
    cmd = ['--mpv-' + i.replace('--', '', 1) if is_darwin and is_iina and i.startswith('--') else i for i in cmd]
    logger.info(cmd)
    player = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    activate_window_by_pid(player.pid)

    if not get_stop_sec:
        return

    init_times = 0
    mpv = None
    while init_times <= 3:
        try:
            time.sleep(1)
            mpv = MPV(start_mpv=False, ipc_socket=pipe_name)
            break
        except Exception as e:
            init_times += 1
            logger.error(f'{str(e)[:40]} {init_times=}')

    stop_sec = None
    while True:
        try:
            tmp_sec = mpv.command('get_property', 'time-pos')
            if not tmp_sec:
                print('.', end='')
            else:
                stop_sec = tmp_sec
            time.sleep(0.5)
        except Exception:
            break
    return check_stop_sec(start_sec, stop_sec)


def start_mpc_player(cmd, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    if sub_file:
        # '/dub "伴音名"	载入额外的音频文件'
        cmd += ['/sub', f'"{sub_file}"']
    if start_sec is not None:
        cmd += ['/start', f'"{int(start_sec * 1000)}"']
    if media_title:
        pass
    cmd[1] = f'"{cmd[1]}"'
    cmd += ['/fullscreen', '/play', '/close']
    logger.info(cmd)
    player = subprocess.Popen(cmd, shell=False)
    activate_window_by_pid(player.pid)
    if not get_stop_sec:
        return

    stop_sec = stop_sec_mpc()
    return check_stop_sec(start_sec, stop_sec)


def start_vlc_player(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    is_nt = True if os.name == 'nt' else False
    # '--sub-file=<字符串> --input-title-format=<字符串>'
    cmd = [cmd[0], '-I', 'qt', '--extraintf', 'rc', '--rc-quiet',
           '--rc-host', '127.0.0.1:58010', ] + cmd[1:]
    if sub_file:
        pass
        # cmd.append(f'--sub-file={sub_file}')  # vlc不支持http字幕
    if start_sec is not None:
        cmd += ['--start-time', str(start_sec)]
    if media_title:
        pass
    cmd += ['--fullscreen', 'vlc://quit']
    cmd = cmd if is_nt else [i for i in cmd if i not in ('-I', 'qt', '--rc-quiet')]
    if configs.disable_audio:
        cmd.append('--no-audio')
    logger.info(cmd)
    player = subprocess.Popen(cmd)
    activate_window_by_pid(player.pid)
    if not get_stop_sec:
        return

    stop_sec = stop_sec_vlc()
    return check_stop_sec(start_sec, stop_sec)


def start_potplayer(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    if sub_file:
        cmd.append(f'/sub={sub_file}')
    if start_sec is not None:
        format_time = time.strftime('%H:%M:%S', time.gmtime(int(start_sec)))
        cmd += [f'/seek={format_time}']
    if media_title:
        cmd += [f'/title={media_title}']
    logger.info(cmd)
    player = subprocess.Popen(cmd)
    activate_window_by_pid(player.pid)
    if not get_stop_sec:
        return

    from utils.windows_tool import get_potplayer_stop_sec
    stop_sec = get_potplayer_stop_sec(player.pid)
    return check_stop_sec(start_sec, stop_sec)


def start_dandan_player(cmd: list, start_sec=None, sub_file=None, media_title=None, get_stop_sec=True):
    if sub_file:
        pass
    if media_title:
        cmd[1] += f'|filePath={media_title}'
    if cmd[1].startswith('http'):
        cmd[0] = 'start'
        cmd[1] = 'ddplay:' + urllib.parse.quote(cmd[1])
        subprocess.run(cmd, shell=True)
        is_http = True
        from utils.windows_tool import find_pid_by_process_name
        time.sleep(1)
        activate_window_by_pid(find_pid_by_process_name('dandanplay.exe'))
    else:
        player = subprocess.Popen(cmd)
        activate_window_by_pid(player.pid)
        is_http = False
    logger.info(cmd)

    if not get_stop_sec:
        return

    stop_sec = stop_sec_dandan(start_sec=start_sec, is_http=is_http)
    return check_stop_sec(start_sec, stop_sec)


class MpcHTMLParser(HTMLParser):
    id_value_dict = {}
    _id = None

    def handle_starttag(self, tag: str, attrs: list):
        if attrs and attrs[0][0] == 'id':
            self._id = attrs[0][1]

    def handle_data(self, data):
        if self._id is not None:
            data = int(data) if data.isdigit() else data.strip()
            self.id_value_dict[self._id] = data
            self._id = None


def stop_sec_mpc():
    url = 'http://localhost:13579/variables.html'
    parser = MpcHTMLParser()
    stop_sec = None
    stack = [None, None]
    first_time = True
    while True:
        try:
            time_out = 2 if first_time else 0.2
            first_time = False
            context = requests_urllib(url, decode=True, timeout=time_out)
            parser.feed(context)
            data = parser.id_value_dict
            position = data['position'] // 1000
            stop_sec = position if data['state'] != '-1' else stop_sec
            stack.pop(0)
            stack.append(stop_sec)
        except Exception:
            logger.info('final stop', stack[-2], stack)
            # 播放器关闭时，webui 可能返回 0
            return stack[-2]
        time.sleep(0.3)


def stop_sec_vlc():
    time.sleep(1)
    stop_sec = None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        sock.connect(('127.0.0.1', 58010))
        while True:
            try:
                sock.sendall(bytes('get_time' + '\n', "utf-8"))
                received = sock.recv(1024).decode().replace('>', '').strip()
                # print('<-', received, '->')
                if len(received.splitlines()) == 1 and received.isnumeric():
                    stop_sec = received
                    time.sleep(0.3)
            except Exception:
                logger.info('stop', stop_sec)
                sock.close()
                return stop_sec
            time.sleep(0.1)


def stop_sec_dandan(start_sec=None, is_http=None):
    config = configs.raw
    dandan = config['dandan']
    api_key = dandan['api_key']
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else None
    close_percent = float(dandan.get('close_at', '100')) / 100
    stop_sec = None
    base_url = f'http://127.0.0.1:{dandan["port"]}'
    status = f'{base_url}/api/v1/current/video'
    time.sleep(5)
    from utils.windows_tool import find_pid_by_process_name, process_is_running_by_pid
    pid = find_pid_by_process_name('dandanplay.exe')
    while True:
        try:
            if requests_urllib(status, headers=headers, decode=True, timeout=0.2):
                break
        except Exception:
            print('.', end='')
            if not process_is_running_by_pid(pid):
                logger.info('dandan player exited')
                return start_sec
            time.sleep(0.3)
    if start_sec and is_http and dandan.getboolean('http_seek'):
        seek_time = f'{base_url}/api/v1/control/seek/{start_sec * 1000}'
        requests_urllib(seek_time, headers=headers)
    logger.info('\n', 'dandan api started')
    while True:
        try:
            response = requests_urllib(status, headers=headers, decode=True, timeout=0.2)
            data = json.loads(response)
            position = data['Position']
            duration = data['Duration']
            tmp_sec = int(duration * position // 1000)
            stop_sec = tmp_sec if tmp_sec else stop_sec
            if position > close_percent:
                logger.info('kill dandan by percent')
                os.kill(pid, signal.SIGABRT)
            elif position > 0.98:
                break
            else:
                time.sleep(0.5)
            logger.debug(tmp_sec, stop_sec, duration, round(position, 2), close_percent)
        except Exception:
            if process_is_running_by_pid(pid):
                logger.info('dandan exception found')
                time.sleep(0.5)
                continue
            break
    return stop_sec


player_function_dict = dict(mpv=start_mpv_player,
                            iina=start_mpv_player,
                            mpc=start_mpc_player,
                            vlc=start_vlc_player,
                            potplayer=start_potplayer,
                            dandanplay=start_dandan_player)
