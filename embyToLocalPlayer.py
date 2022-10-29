import multiprocessing
import threading
from http.server import BaseHTTPRequestHandler

from utils.downloader import DownloadManager
from utils.players import player_function_dict
from utils.tools import *


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
        configs.update()
        if 'ToLocalPlayer' in self.path:
            data = parse_received_data_emby(data) if self.path.startswith('emby') else parse_received_data_emby(data)
            update_server_playback_progress(stop_sec=data['start_sec'], data=data)
            if configs.disable_gui_by_netloc(data['netloc']):
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
        if self.path in ('/gui', '/dl'):
            gui_cmd = data['gui_cmd']
            logger.info(self.path, gui_cmd)
            thread_dict[gui_cmd].start()
        elif 'ToLocalPlayer' in self.path:
            if configs.gui_is_enable:
                from utils.gui import show_ask_button
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


def start_play(data):
    global player_is_running
    if player_is_running:
        logger.error('player_is_running, skip')
        return
    mount_disk_mode = data['mount_disk_mode']
    media_path = data['media_path']
    start_sec = data['start_sec']
    sub_file = data['sub_file']
    media_title = data['media_title']

    cmd = get_player_and_replace_path(media_path, data.get('file_path'))['cmd']
    player_path_lower = cmd[0].lower()
    # 播放器特殊处理
    player_is_running = True
    player_name = [i for i in player_function_dict if i in player_path_lower]
    if player_name:
        player_name = player_name[0]
        player_function = player_function_dict[player_name]
        if player_name == 'vlc':
            # cmd.append('--no-video-title-show')
            if mount_disk_mode:
                # cmd.append(f'--input-title-format={cmd[1]}')
                cmd[1] = f'file:///{cmd[1]}'
            else:
                cmd.append(f'--input-title-format={media_title}')
                cmd.append(f'--video-title={media_title}')
        stop_sec = player_function(cmd=cmd, start_sec=start_sec, sub_file=sub_file, media_title=media_title)
        logger.info('stop_sec', stop_sec)
        update_server_playback_progress(stop_sec=stop_sec, data=data)
        if configs.gui_is_enable and stop_sec / data['total_sec'] * 100 > configs.raw.getfloat('gui', 'delete_at'):
            if media_path.startswith(configs.raw['gui']['cache_path']):
                logger.info('watched, delete cache')
                threading.Thread(target=dl_manager.delete, args=(data,), daemon=True).start()
    else:
        logger.info(cmd)
        player = subprocess.Popen(cmd, shell=False)
        activate_window_by_pid(player.pid)
    player_is_running = False


if __name__ == '__main__':
    dl_manager = DownloadManager(configs.cache_path, speed_limit=configs.speed_limit)
    cwd = os.path.dirname(__file__)
    file_name = os.path.basename(__file__)[:-3]
    player_is_running = False
    kill_multi_process(name_re=f'({file_name}.py|autohotkey_tool|' +
                               r'mpv.*exe|mpc-.*exe|vlc.exe|PotPlayer.*exe|dandanplay.exe|' +
                               r'/IINA|/VLC|/mpv)',
                       not_re='(screen|tmux|greasyfork|github)')
    logger = MyLogger()
    logger.info(__file__)
    run_server(_RequestHandler)
