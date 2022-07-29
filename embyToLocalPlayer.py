import json
import os.path
import signal
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from configparser import ConfigParser
from http.server import HTTPServer, BaseHTTPRequestHandler

from python_mpv_jsonipc import MPV


class PlayerRunningState(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global player_is_running
        player_is_running = True
        time.sleep(0.1)
        player_is_running = False


class _RequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('content-length'))
        data = json.loads(self.rfile.read(length))
        self._set_headers()
        self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
        if player_is_running:
            log('reject post when running')
            return
        if 'embyToLocalPlayer' in self.path and not player_is_running:
            emby_to_local_player(data)
        elif 'openFolder' in self.path:
            open_local_folder(data)
        elif 'playMediaFile' in self.path:
            play_media_file(data)
        else:
            log(self.path, ' not allow')
            return json.dumps({'success': True}).encode('utf-8')


def log(*args):
    if not enable_log:
        return
    log_str = f'{time.ctime()} {str(args)}\n'
    if print_only:
        print(log_str, end='')
        return
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(log_str)


def open_local_folder(data):
    path = data['info'][0]['content_path']
    transfer_path = get_exe_and_replace_path(path)[1]
    explore(transfer_path)


def play_media_file(data):
    save_path = data['info'][0]['save_path']
    big_file = sorted(data['file'], key=lambda i: i['size'], reverse=True)[0]['name']
    path = os.path.join(save_path, big_file)
    cmd = get_exe_and_replace_path(path)
    subprocess.run(cmd)


def explore(path):
    if os.name != 'nt':
        log('open folder only work in windows')
    # filebrowser = os.path.join(os.getenv('WINDIR'), 'explorer.exe')
    path = os.path.normpath(path)
    # cmd = [filebrowser, path] if os.path.isdir(path) else [filebrowser, '/select,', path]
    cmd = f'explorer "{path}"' if os.path.isdir(path) else f'explorer /select, "{path}"'
    os.system(cmd)


def get_exe_and_replace_path(media_path):
    config = ConfigParser()
    config.read(ini, encoding='utf-8')
    player = config['emby']['player']
    exe = config['exe'][player]
    src = config['src']
    dst = config['dst']
    log(media_path, 'raw')
    # 貌似是有序字典
    for k, src_prefix in src.items():
        if src_prefix in media_path:
            dst_prefix = dst[k]
            media_path = media_path.replace(src_prefix, dst_prefix, 1)
            break
    result = [exe, media_path]
    log(result, 'cmd')
    return result


def requests_urllib(host, params, _json):
    _json = json.dumps(_json).encode('utf-8')
    params = urllib.parse.urlencode(params)
    host = host + '?' + params
    req = urllib.request.Request(host)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    urllib.request.urlopen(req, _json)


def active_window_by_pid(pid, ahk='active_video_player.ahk'):
    script_path = os.path.join(cwd, ahk)
    if os.name != 'nt' or not os.path.exists(script_path):
        return
    subprocess.run([script_path, str(pid)], shell=True)


def emby_to_local_player(info):
    url = info['url']
    info = info['data']
    url = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(url.query))
    query: dict
    item_id = [i for i in url.path.split('/') if i.isdigit()][0]
    path_id = query.get('MediaSourceId')
    path_list = info['MediaSources']
    if path_id:
        path = [i['Path'] for i in path_list if i['Id'] == path_id][0]
    else:
        path = path_list[0]['Path']
    seek = query['StartTimeTicks']
    start_sec = int(seek) / (10 ** 7) if seek else 0
    cmd = get_exe_and_replace_path(path)

    def change_emby_play_position(sec):
        key = query['X-Emby-Token']
        host = url.netloc
        scheme = url.scheme
        ticks = sec * 10 ** 7
        requests_urllib(f'{scheme}://{host}/emby/Sessions/Playing',
                        params={'X-Emby-Token': key},
                        _json={'ItemId': item_id})
        requests_urllib(f'{scheme}://{host}/emby/Sessions/Playing/Stopped',
                        params={'X-Emby-Token': key},
                        _json={'PositionTicks': ticks,
                               'ItemId': item_id
                               })

    if 'mpv.exe' in cmd[0]:
        pipe_name = 'embyToMpv'
        cmd.append(f'--start={start_sec}')
        cmd.append(fr'--input-ipc-server=\\.\pipe\{pipe_name}')
        mpv_proc = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE)
        try:
            mpv = MPV(start_mpv=False, ipc_socket=pipe_name)
        except Exception as e:
            print(e)
            time.sleep(1)
            mpv = MPV(start_mpv=False, ipc_socket=pipe_name)

        active_window_by_pid(mpv_proc.pid)

        stop_sec = 0
        while True:
            try:
                _ = mpv.command('get_property', 'time-pos')
                if not _:
                    print('top_sec is error')
                else:
                    stop_sec = _
                time.sleep(0.5)
            except Exception:
                break

        stop_sec = int(stop_sec) - 2 if stop_sec > 5 else int(start_sec)
        log('stop_sec', stop_sec)
        change_emby_play_position(stop_sec)
    else:
        player = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE)
        active_window_by_pid(player.pid)
    PlayerRunningState().start()


def list_pid_cmd(str_in='') -> list:
    cmd = 'Get-WmiObject Win32_Process | Select ProcessId,CommandLine'
    proc = subprocess.run(['powershell', '-Command', cmd], capture_output=True, encoding='gbk')
    if proc.returncode != 0:
        return []
    result = []
    for line in proc.stdout.splitlines():
        line = line.strip().split(maxsplit=1)
        if len(line) < 2 or not line[0].isdecimal():
            continue
        if not str_in or (str_in and str_in in line[1]):
            result.append(line)
    result = [(int(pid), _cmd) for pid, _cmd in result]
    return result


def kill_multi_process(name):
    if os.name != 'nt':
        return
    my_pid = os.getpid()
    pid_cmd = list_pid_cmd(name)
    for pid, _ in pid_cmd:
        if pid != my_pid:
            os.kill(pid, signal.SIGABRT)


def run_server():
    server_address = ('127.0.0.1', 58000)
    httpd = HTTPServer(server_address, _RequestHandler)
    print('serving at %s:%d' % server_address, file_name)
    httpd.serve_forever()


if __name__ == '__main__':
    enable_log = True
    print_only = True
    cwd = os.path.dirname(__file__)
    file_name = os.path.basename(__file__)[:-3]
    ini = os.path.join(cwd, f'{file_name}.ini')
    log_path = os.path.join(cwd, f'{file_name}.log')
    player_is_running = False
    kill_multi_process(file_name + '.py')
    log(__file__)
    run_server()
