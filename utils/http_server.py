import json
import multiprocessing
import os
import re
import socket
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socketserver import ThreadingMixIn

from utils.data_parser import parse_received_data_emby, parse_received_data_plex, list_episodes
from utils.downloader import DownloadManager
from utils.net_tools import update_server_playback_progress, sync_third_party_for_eps
from utils.player_manager import PlayerManager
from utils.players import start_player_func_dict, stop_sec_func_dict
from utils.tools import (configs, MyLogger, open_local_folder, play_media_file,
                         activate_window_by_pid, get_player_cmd, ThreadWithReturnValue)
from utils.trakt_sync import trakt_api_client

player_is_running = False
logger = MyLogger()
dl_manager = DownloadManager(configs.cache_path, speed_limit=configs.speed_limit)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('223.5.5.5', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'
    return local_ip


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


def run_server(ip='127.0.0.1', port=58000):
    server_token = configs.raw.getboolean('dev', 'listen_on_lan', fallback=False)
    if server_token:
        ip = get_local_ip()
    server_address = (ip, port)
    httpd = ThreadingHTTPServer(server_address, UserScriptRequestHandler)
    logger.info('serving at http://%s:%d' % server_address)
    httpd.serve_forever()


class UserScriptRequestHandler(BaseHTTPRequestHandler):

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
        configs.update()
        if 'ToLocalPlayer' in self.path:
            data = parse_received_data_emby(data) if self.path.startswith('/emby') else parse_received_data_plex(data)
            logger.info(f"server={data['server']}/{data.get('server_version')} {data['mount_disk_mode']=}")
            if configs.check_str_match(_str=data['netloc'], section='gui', option='except_host'):
                threading.Thread(target=start_play, args=(data,), daemon=True).start()
                return True
        thread_dict = {
            'play': threading.Thread(target=start_play, args=(data,)),
            'play_check': threading.Thread(target=dl_manager.play_check, args=(data,)),
            'download_play': threading.Thread(target=dl_manager.download_play, args=(data,)),
            'download_not_play': threading.Thread(target=dl_manager.download_play, args=(data, False)),
            'download_only': threading.Thread(target=dl_manager.download_only, args=(data,)),
            'delete_by_id': threading.Thread(target=dl_manager.delete, args=({}, data.get('_id'))),
            'delete': threading.Thread(target=dl_manager.delete, args=(data,)),
            'resume_or_pause': threading.Thread(target=dl_manager.resume_or_pause, args=(data,)),
        }
        [setattr(t, 'daemon', True) for t in thread_dict.values()]
        if self.path in ('/gui', '/dl', '/pl'):
            gui_cmd = data['gui_cmd']
            logger.info(self.path, gui_cmd)
            thread_dict[gui_cmd].start()
        elif 'ToLocalPlayer' in self.path:
            if configs.gui_is_enable:
                if configs.raw.get('gui', 'enable_path'):
                    if not configs.check_str_match(data['file_path'], 'gui', 'enable_path', log_by=False):
                        thread_dict['play'].start()
                        return True
                from utils.gui import show_ask_button
                logger.info('show ask button')
                if configs.platform != 'Darwin':
                    threading.Thread(target=show_ask_button, args=(data,), daemon=True).start()
                else:
                    multiprocessing.Process(target=show_ask_button, args=(data,), daemon=True).start()
            else:
                thread_dict['play'].start()
        elif 'openFolder' in self.path:
            open_local_folder(data)
        elif 'playMediaFile' in self.path:
            play_media_file(data)
        else:
            logger.error(self.path, ' not allow')
            return json.dumps({'success': True}).encode('utf-8')

    def do_OPTIONS(self):
        pass

    def do_GET(self):
        if self.path in ['/', '/favicon.ico']:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'Server is running')
            return
        if self.path.startswith('/play_media_file'):
            self.play_media_file()
            return
        if self.path.startswith('/trakt_auth'):
            parsed_path = urllib.parse.urlparse(self.path)
            query = dict(urllib.parse.parse_qsl(parsed_path.query))
            if received_code := query.get('code'):
                trakt_api_client(received_code)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'etlp: trakt auth success')
            logger.info(f'trakt: auth success')
            return
        logger.info(f'path invalid {self.path=}')

    def play_media_file(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(parsed_path.query))

        req_token = query.get('token', '')
        server_token = configs.raw.get('dev', 'http_server_token', fallback='')
        if req_token != server_token:
            logger.info(f'req_token invalid: {req_token=} {server_token=}')
            return

        video_path = urllib.parse.unquote(query['file_path'])

        video_ext = ['webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'rrc', 'gifv', 'mng', 'mov', 'avi', 'qt', 'wmv', 'yuv',
                     'rm', 'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mp2', 'mpeg', 'mpe', 'mpv', 'm4v', 'svi', '3gp',
                     '3g2', 'mxf', 'roq', 'nsv', 'flv', 'f4v', 'f4p', 'f4a', 'f4b', 'mod']
        sub_ext = ['srt', 'sub', 'ass', 'ssa', 'vtt', 'sbv', 'smi', 'sami', 'mpl', 'txt', 'dks', 'pjs', 'stl', 'usf',
                   'cdg', 'idx', 'ttml']
        valid_ext = tuple(video_ext + sub_ext)

        if not video_path.endswith(valid_ext):
            logger.info(f'ext invalid: {video_path}')
            return

        if not os.path.exists(video_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'File not found')
            return

        file_size = os.path.getsize(video_path)
        chunk_size = 8 * 1024 * 1024
        range_header = self.headers.get('Range', None)

        if range_header:
            start, end = self.parse_range_header(range_header, file_size)
            logger.info(f'range={start}-{end} | {video_path}')
            if start >= file_size or end >= file_size or start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{file_size}')
                self.end_headers()
                return

            self.send_response(206)
            self.send_header('Content-type', 'octet-stream')
            self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
            self.send_header('Content-Length', str(end - start + 1))
            self.end_headers()

            with open(video_path, 'rb') as file:
                file.seek(start)
                bytes_to_read = end - start + 1
                while bytes_to_read > 0:
                    chunk = file.read(min(chunk_size, bytes_to_read))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except ConnectionError:
                        break
                    bytes_to_read -= len(chunk)

        else:
            logger.info(f'range: 0- | {video_path}')
            self.send_response(200)
            self.send_header('Content-type', 'octet-stream')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()

            with open(video_path, 'rb') as file:
                while chunk := file.read(chunk_size):
                    try:
                        self.wfile.write(chunk)
                    except ConnectionError:
                        break

    @staticmethod
    def parse_range_header(range_header, file_size):
        match = re.match(r'bytes=(\d*)-(\d*)', range_header)
        if match:
            start = match.group(1)
            end = match.group(2)
            start = int(start) if start else 0
            end = int(end) if end else file_size - 1
            return start, end
        return 0, file_size - 1


def start_play(data):
    global player_is_running
    if player_is_running:
        logger.error('player_is_running, skip. You may want to disable one_instance_mode, see detail in config file')
        return
    file_path = data['file_path']
    start_sec = data['start_sec']
    sub_file = data['sub_file']
    media_title = data['media_title']
    mount_disk_mode = data['mount_disk_mode']
    eps_data_thread = ThreadWithReturnValue(target=list_episodes, args=(data,))
    eps_data_thread.start()

    cmd = get_player_cmd(media_path=data['media_path'], file_path=file_path)
    player_path = cmd[0]
    player_path_lower = player_path.lower()
    # 播放器特殊处理
    player_is_running = True if configs.raw.getboolean('dev', 'one_instance_mode', fallback=True) else False
    player_alias_dict = {'ddplay': 'dandanplay'}
    legal_player_name = list(start_player_func_dict) + list(player_alias_dict)
    player_name = [i for i in legal_player_name if i in player_path_lower]
    if player_name:
        player_name = player_name[0]
        player_name = player_alias_dict.get(player_name, player_name)
        if configs.check_str_match(_str=data['netloc'], section='playlist', option='enable_host') \
                and player_name in ('mpv', 'vlc', 'mpc', 'potplayer', 'iina') \
                or (player_name == 'dandanplay' and mount_disk_mode):
            player_manager = PlayerManager(data=data, player_name=player_name, player_path=player_path)
            player_manager.start_player(cmd=cmd, start_sec=start_sec, sub_file=sub_file, media_title=media_title,
                                        mount_disk_mode=mount_disk_mode, data=data)
            eps_data = eps_data_thread.join()
            player_manager.playlist_add(eps_data=eps_data)
            player_manager.update_playlist_time_loop()
            player_manager.update_playback_for_eps()
            player_is_running = False
            return

        player_function = start_player_func_dict[player_name]
        stop_sec_kwargs = player_function(cmd=cmd, start_sec=start_sec, sub_file=sub_file, media_title=media_title,
                                          mount_disk_mode=mount_disk_mode, data=data)
        stop_sec = stop_sec_func_dict[player_name](**stop_sec_kwargs)
        logger.info('stop_sec', stop_sec)
        if stop_sec is None:
            player_is_running = False
            return
        update_server_playback_progress(stop_sec=stop_sec, data=data)

        eps_data = eps_data_thread.join()
        current_ep = [i for i in eps_data if i['file_path'] == data['file_path']][0]
        current_ep['_stop_sec'] = stop_sec
        for provider in 'trakt', 'bangumi':
            if configs.raw.get(provider, 'enable_host', fallback=''):
                threading.Thread(target=sync_third_party_for_eps,
                                 kwargs={'eps': [current_ep], 'provider': provider}, daemon=True).start()

        if configs.gui_is_enable \
                and stop_sec / data['total_sec'] * 100 > configs.raw.getfloat('gui', 'delete_at', fallback=99.9) \
                and file_path.startswith(configs.raw['gui']['cache_path']):
            logger.info('watched, delete cache')
            threading.Thread(target=dl_manager.delete, args=(data,), daemon=True).start()
    else:
        logger.info('run as not support player mod')
        logger.info(cmd)
        player = subprocess.Popen(cmd)
        activate_window_by_pid(player.pid)
    player_is_running = False
