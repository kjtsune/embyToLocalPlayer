import os
import socket
import sys
import threading
import traceback


try:
    sys.path.insert(0, os.path.dirname(__file__))
except Exception:
    pass

from utils.downloader import prefetch_resume_tv
from utils.http_server import run_server
from utils.tools import (configs, MyLogger, kill_multi_process, clean_tmp_dir)
from utils.net_tools import check_redirect_cache_expired_loop


def port_is_available(ip='127.0.0.1', port=58000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((ip, port))
        except OSError:
            return False
    return True


if __name__ == '__main__':
    try:
        os.chdir(configs.cwd)
        configs.print_version()
        logger = MyLogger()

        if configs.raw.getboolean('dev', 'kill_process_at_start', fallback=True):
            if os.name == 'nt':
                logger.info('windows start: skip killing embyToLocalPlayer.py, only clean player/helper processes')
                kill_multi_process(name_re=f'(autohotkey_tool|' +
                                       r'mpv.*exe|mpc-.*exe|vlc.exe|PotPlayer.*exe|' +
                                       r'/IINA|/VLC|/mpv)',
                                   not_re='(tmux|greasyfork|github)')
            else:
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

        logger.info(__file__)
        clean_tmp_dir()
        configs.necessary_setting_when_server_start()
        listen_ip = '127.0.0.1'
        if not configs.raw.getboolean('dev', 'listen_on_localhost', fallback=True):
            from utils.http_server import get_machine_ip
            listen_ip = get_machine_ip()
        if not port_is_available(ip=listen_ip, port=configs.server_port):
            logger.error(f'server port already in use: http://{listen_ip}:{configs.server_port}')
            logger.error('stop starting new instance. close the old instance or change [dev] server_port in ini.')
            sys.exit(1)
        threading.Thread(target=prefetch_resume_tv, daemon=True).start()
        threading.Thread(target=check_redirect_cache_expired_loop, daemon=True).start()
        run_server(port=configs.server_port)  # main entry: utils.http_server.py
    except Exception:
        traceback.print_exc()
        raise
