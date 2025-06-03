import os
import sys
import threading


try:
    sys.path.insert(0, os.path.dirname(__file__))
except Exception:
    pass

from utils.downloader import prefetch_resume_tv
from utils.http_server import run_server
from utils.tools import (configs, MyLogger, kill_multi_process, clean_tmp_dir)
from utils.net_tools import check_redirect_cache_expired_loop

if __name__ == '__main__':
    os.chdir(configs.cwd)
    configs.print_version()
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
    configs.necessary_setting_when_server_start()
    threading.Thread(target=prefetch_resume_tv, daemon=True).start()
    threading.Thread(target=check_redirect_cache_expired_loop, daemon=True).start()
    run_server()  # 主要逻辑入口：utils.http_server.py
