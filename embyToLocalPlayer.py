import json
import multiprocessing
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler

from utils.downloader import DownloadManager, prefetch_resume_tv
from utils.net_tools import update_server_playback_progress, run_server
from utils.players import (player_start_func_dict, PlayerManager, stop_sec_function_dict, list_episodes,
                           sync_third_party_for_eps)
from utils.tools import (configs, logger_setup, MyLogger, open_local_folder, play_media_file,
                         kill_multi_process, activate_window_by_pid, clean_tmp_dir,
                         parse_received_data_emby, parse_received_data_plex,
                         get_player_cmd, ThreadWithReturnValue)


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
            data = parse_received_data_emby(data) if self.path.startswith('/emby') else parse_received_data_plex(data)
            logger_setup(data=data)
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


def start_play(data):
    global player_is_running
    if player_is_running:
        logger.error('player_is_running, skip')
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
    player_is_running = True if configs.raw.getboolean('dev', 'one_instance_mode', fallback=False) else False
    player_name = [i for i in player_start_func_dict if i in player_path_lower]
    if player_name:
        player_name = player_name[0]
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

        player_function = player_start_func_dict[player_name]
        stop_sec_kwargs = player_function(cmd=cmd, start_sec=start_sec, sub_file=sub_file, media_title=media_title,
                                          mount_disk_mode=mount_disk_mode, data=data)
        stop_sec = stop_sec_function_dict[player_name](**stop_sec_kwargs)
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
        logger.info(cmd)
        player = subprocess.Popen(cmd)
        activate_window_by_pid(player.pid)
    player_is_running = False


if __name__ == '__main__':
    os.chdir(configs.cwd)
    player_is_running = False
    dl_manager = DownloadManager(configs.cache_path, speed_limit=configs.speed_limit)
    if configs.raw.getboolean('dev', 'kill_process_at_start', fallback=True):
        kill_multi_process(name_re=f'(embyToLocalPlayer.py|autohotkey_tool|' +
                                   r'mpv.*exe|mpc-.*exe|vlc.exe|PotPlayer.*exe|' +
                                   r'/IINA|/VLC|/mpv)',
                           not_re='(tmux|greasyfork|github)')

    for _provider in 'trakt', 'bangumi':
        if configs.raw.get(_provider, 'enable_host', fallback=''):
            from utils.trakt_sync import trakt_sync_main
            from utils.bangumi_sync import bangumi_sync_main

            threading.Thread(target={'trakt': trakt_sync_main, 'bangumi': bangumi_sync_main}[_provider],
                             kwargs={'test': True}, daemon=True).start()

    logger = MyLogger()
    logger.info(__file__)
    clean_tmp_dir()
    threading.Thread(target=prefetch_resume_tv, daemon=True).start()
    run_server(_RequestHandler)
