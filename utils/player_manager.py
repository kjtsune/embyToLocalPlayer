import os
import re
import threading
import time
import urllib.parse

from utils.configs import configs, MyLogger
from utils.downloader import Downloader
from utils.emby_api_thin import EmbyApiThin
from utils.net_tools import (get_redirect_url, requests_urllib, realtime_playing_request_sender,
                             update_server_playback_progress, sync_third_party_for_eps, check_miss_runtime_start_sec)
from utils.players import start_player_func_dict, playlist_func_dict, stop_sec_func_dict, prefetch_data
from utils.tools import activate_window_by_pid

logger = MyLogger()


class BaseInit:
    def __init__(self, data, player_name=None, player_path=None):
        self.data = data
        self.player_name = player_name
        self.player_path = player_path
        self.player_kwargs = {}
        self.playlist_data = {}
        self.playlist_time = {}
        self.playlist_total_sec = {}
        self.is_http_sub = bool(data.get('sub_file'))
        self.emby_thin = EmbyApiThin(data)


class BaseManager(BaseInit):

    def make_start_sec_correct(self):
        # emby 缺少视频时长时无法储存起播时间
        start_sec, total_sec = self.data['start_sec'], self.data['total_sec']
        if start_sec != 0 or total_sec != 3600 * 24:
            return start_sec
        netloc, item_id, basename = self.data['netloc'], self.data['item_id'], self.data['basename']
        start_sec = check_miss_runtime_start_sec(netloc, item_id, basename)
        logger.info(f'strm: make_start_sec_correct : {start_sec=}')
        return start_sec

    def start_player(self, **kwargs):
        kwargs['start_sec'] = self.make_start_sec_correct() or 0
        media_title = kwargs['media_title']
        if 'pot' in self.player_name and configs.media_title_translate(
                media_title=media_title, get_trans=True, player_path=self.player_path):
            if self.data['mount_disk_mode']:
                self.data['media_title'], kwargs['media_title'] = self.data['basename'], None
            else:
                media_title = configs.media_title_translate(media_title=media_title, player_path=self.player_path,
                                                            log=False)
                self.data['media_title'], kwargs['media_title'] = media_title, media_title
        try:
            self.player_kwargs = start_player_func_dict[self.player_name](**kwargs)
        except FileNotFoundError:
            raise FileNotFoundError(f'player not exists, check config ini file, {kwargs["cmd"][0]}') from None

    def playlist_add(self, eps_data=None):
        limit = configs.raw.getint('playlist', 'item_limit', fallback=-1)
        if self.data.get('gui_cmd') and not self.data.get('gui_without_confirm'):
            logger.info('disable playlist: cuz gui_cmd found')
            limit = 0
        if limit >= 0:
            self.player_kwargs['limit'] = limit

        if 'pot' in self.player_name and not self.data['mount_disk_mode']:
            if trans := configs.media_title_translate(get_trans=True, player_path=self.player_path):
                for ep in eps_data:
                    media_title = ep['media_title']
                    if '  |  ' in media_title:
                        ep['media_title'] = media_title.translate(trans)

        self.playlist_data = playlist_func_dict[self.player_name](data=self.data, eps_data=eps_data,
                                                                  **self.player_kwargs)

    def http_sub_auto_next_ep_time_loop(self, key_field):
        playlist_data = tuple(self.playlist_data.items())
        fist_ep = True
        for index, (key, ep) in enumerate(playlist_data):
            if fist_ep and key != self.data[key_field]:
                continue
            next_title, next_ep = playlist_data[index + 1] if index < len(playlist_data) - 1 else (None, None)
            stop_sec = stop_sec_func_dict[self.player_name](stop_sec_only=True, **self.player_kwargs)
            self.playlist_time[key] = stop_sec
            fist_ep = False
            if not next_ep or not stop_sec:
                break
            next_media_title = next_ep['media_title']
            if stop_sec / ep['total_sec'] < 0.9:
                logger.info(f'skip play {next_media_title}, because watch progress < 0.9')
                break
            # if show_confirm_button('Click To Stop Play Next EP', 200, 40, result=True, fallback=False, timeout=2):
            #     logger.info('Stop Play Next EP by button')
            #     break
            self.player_kwargs = start_player_func_dict[self.player_name](
                cmd=[self.player_path, next_ep['media_path']], sub_file=next_ep.get('sub_file'),
                media_title=next_media_title, mount_disk_mode=False)
            activate_window_by_pid(self.player_kwargs['pid'])
            logger.info(f'auto play: {next_media_title}')

    def update_playlist_time_loop(self):
        if configs.raw.getboolean('dev', 'http_sub_auto_next_ep', fallback=False) and (
                (self.is_http_sub and self.player_name == 'potplayer')
                or (self.is_http_sub and self.player_name == 'vlc' and os.name != 'nt')):
            key_field_map = {'potplayer': 'media_title', 'vlc': 'media_basename'}
            logger.info('disable playlist cuz http sub, auto next ep mode enabled')
            self.http_sub_auto_next_ep_time_loop(key_field=key_field_map[self.player_name])
        else:
            stop_fun_res = stop_sec_func_dict[self.player_name](stop_sec_only=False, **self.player_kwargs)
            if isinstance(stop_fun_res, tuple):
                self.playlist_time, self.playlist_total_sec = stop_fun_res
            else:
                self.playlist_time = stop_fun_res

        # 未兼容播放器多开，暂不处理
        prefetch_data['on'] = False
        prefetch_data['stop_sec_dict'].clear()

    def prefetch_next_ep_playback_info(self):
        try:
            played_eps = [self.playlist_data.get(key) for key in self.playlist_time]
            played_eps = sorted([i for i in played_eps if i], key=lambda d: d['order'])
            next_ep = [i for i in self.playlist_data.values() if i['order'] == played_eps[0]['order'] + 1]
        except Exception:  # not played_eps, movie not order
            return
        if next_ep and next_ep[0].get('total_sec') == 3600 * 24:
            next_ep = next_ep[0]
            logger.info(f'prefetch_next_ep_playback_info {next_ep["basename"]}')
            self.emby_thin.get_playback_info(next_ep['item_id'], timeout=60)

    def update_playback_for_eps(self):
        need_update_eps = []
        if not self.playlist_data:
            logger.error(f'skip update progress: playlist_data not found')
            return
        for key, _stop_sec in self.playlist_time.items():
            ep = self.playlist_data.get(key)
            if not ep:
                logger.error(f'skip update progress: {key=} {_stop_sec=} not in playlist_data')
                continue
            if not _stop_sec:
                continue
            start_sec = ep.get('start_sec') or 0
            _stop_sec = int(_stop_sec)
            if abs(_stop_sec - int(start_sec)) < 20:
                logger.info(f"skip update progress, {ep['basename']} start_sec stop_sec too close")
                continue
            ep['_stop_sec'] = _stop_sec
            emby_strm_miss_runtime = bool(ep['server'] != 'plex' and ep['total_sec'] == 3600 * 24)
            mpv_total_sec = self.playlist_total_sec.get(key)
            need_recheck = emby_strm_miss_runtime and bool(not mpv_total_sec or _stop_sec / mpv_total_sec < 0.9)
            if need_recheck:
                # 注意：仅限启用播放列表时候有这些处理，strm 缺失 total_sec 和 缓存播放进度
                netloc, item_id, basename = ep['netloc'], ep['item_id'], ep['basename']
                logger.info('strm: fetching playback info')  # emby 也可能补全媒体信息失败，会返回没有 RunTimeTicks 的。
                _playback_info = self.emby_thin.get_playback_info(item_id, timeout=30)  # Jellyfin 不会在播放中补全媒体信息
                _media_source = [i for i in _playback_info['MediaSources'] if i.get('RunTimeTicks', 0)]
                _total_sec = _media_source and _media_source[0]['RunTimeTicks'] // 10 ** 7 or 0
                if _media_source:
                    # 注意此处 id 变动了，为了确保回传成功，目前没不良影响。多版本不同支线的情况极少，emby 自身也是没区分。
                    ep['item_id'] = _media_source[0]['ItemId']
                    logger.info('strm: total_sec found by recheck server data')
                else:
                    check_miss_runtime_start_sec(netloc, item_id, basename, stop_sec=_stop_sec)
                    logger.info(f'strm: recheck failed, cache start_sec={_stop_sec} | {basename}')

                total_sec = self.playlist_total_sec.get(key) or _total_sec
                _skip = True
                if total_sec:
                    ep['total_sec'] = total_sec
                    if _stop_sec / total_sec > 0.9 or _total_sec:
                        update_server_playback_progress(stop_sec=_stop_sec, data=ep)
                        _skip = False
                _skip and logger.info(f"skip update progress, {ep['basename']} miss runtime data")
            else:
                if emby_strm_miss_runtime and mpv_total_sec:
                    ep['total_sec'] = mpv_total_sec
                update_server_playback_progress(stop_sec=_stop_sec, data=ep)
            need_update_eps.append(ep)
        threading.Thread(target=self.prefetch_next_ep_playback_info, daemon=True).start()
        if not need_update_eps:
            return
        for provider in 'trakt', 'bangumi':
            if need_update_eps[0]['total_sec'] == 3600 * 24:
                logger.error('trakt, bgm disabled: cuz miss emby runtime data')
                break
            if configs.raw.get(provider, 'enable_host', fallback=''):
                threading.Thread(target=sync_third_party_for_eps,
                                 kwargs={'eps': need_update_eps, 'provider': provider}, daemon=True).start()


class PrefetchManager(BaseInit):  # 未兼容播放器多开，暂不处理

    def mpv_cache_via_nas_loop(self):
        mpv = self.player_kwargs.get('mpv')
        if not mpv or not configs.check_str_match(self.data['netloc'], 'dev', 'playing_feedback_host', log=True):
            return
        if self.data['server'] == 'plex':
            logger.info('playing_feedback not support plex, skip')
            return
        stop_sec_dict = prefetch_data['stop_sec_dict']
        prefetch_data['on'] = True

        source_id = re.compile(r'(?<=MediaSourceId=)\w+')

        while prefetch_data['on']:
            try:
                key = mpv.command('get_property', 'media-title')
                speed = mpv.command('get_property', 'speed')
            except Exception:
                break

    def realtime_playing_feedback_loop(self):
        mpv = self.player_kwargs.get('mpv')
        if not mpv or not configs.check_str_match(self.data['netloc'], 'dev', 'playing_feedback_host', log=True):
            return
        if self.data['server'] == 'plex':
            logger.info('playing_feedback not support plex, skip')
            return
        if self.data.get('total_sec') == 3600 * 24:
            # 会造成意外完成播放
            logger.info('playing_feedback not support strm, skip')
            return
        stop_sec_dict = prefetch_data['stop_sec_dict']
        prefetch_data['on'] = True
        last_key = None
        req_sec = 0
        interval = 5
        pause_sec = 0
        last_ep = None
        while prefetch_data['on']:
            try:
                key = mpv.command('get_property', 'media-title')
                speed = mpv.command('get_property', 'speed')
                if mpv.command('get_property', 'pause'):
                    pause_sec += interval
                else:
                    pause_sec = 0
            except Exception:
                break
            cur_sec = stop_sec_dict.get(key)
            ep = self.playlist_data.get(key)
            if not all([cur_sec, ep]):
                time.sleep(0.5)
                continue
            if key != last_key:
                if last_ep:
                    last_sec = stop_sec_dict[last_key]
                    logger.trace(f'updating end {last_sec=} {last_ep["basename"]}')
                    realtime_playing_request_sender(data=last_ep, cur_sec=last_sec, method='end')
                    last_ep['update_success'] = True
                realtime_playing_request_sender(data=ep, cur_sec=cur_sec, method='start')
                last_ep = ep
                last_key = key
                req_sec = cur_sec
                time.sleep(interval)
                logger.trace(f'updating start {cur_sec=} {last_ep["basename"]}')
                continue
            after_sec = cur_sec - req_sec
            if 180 < pause_sec or 0 < after_sec < 30 * speed:  # 尽量增加汇报间隔
                time.sleep(interval)
                continue
            realtime_playing_request_sender(data=ep, cur_sec=cur_sec)
            req_sec = cur_sec
            time.sleep(interval)

    def redirect_next_ep_loop(self):
        mpv = self.player_kwargs.get('mpv')
        stream_netloc = urllib.parse.urlparse(self.data['stream_url']).netloc
        if not mpv or not configs.check_str_match(stream_netloc, 'dev', 'redirect_check_host', log=False):
            return
        if len(self.playlist_data) == 1:
            return

        done_list = []
        stop_sec_dict = prefetch_data['stop_sec_dict']
        prefetch_data['on'] = True
        while prefetch_data['on']:
            if self.data.get('gui_without_confirm'):
                return
            for key, stop_sec in stop_sec_dict.copy().items():
                ep = self.playlist_data.get(key)
                if not ep:
                    continue
                if not ep['media_path'].startswith('http'):
                    return
                if not key or not stop_sec or key in done_list:
                    continue
                if stop_sec / ep['total_sec'] < 0.5 and ep['total_sec'] != 86400:
                    continue
                # mix_sO 可能造成 index 重复
                # next_ep = [e for e in self.playlist_data.values() if e['index'] == ep['index'] + 1]
                # 字典目前保持插入顺序
                # playlist_data 条目数量可能大于实际数量。(目前 mpv 不会)
                list_playlist_data = list(self.playlist_data.values())
                if ep == list_playlist_data[-1]:
                    break
                start_file_index = list_playlist_data.index(
                    [e for e in list_playlist_data if e.get('is_start_file')][0])
                next_ep_index = list_playlist_data.index(ep) + 1
                if next_ep_index <= start_file_index:
                    logger.info(f'redirect_next_ep: not support pre ep, skip {next_ep_index}')
                    done_list.append(key)
                    continue
                next_ep_key = list(self.playlist_data.keys())[next_ep_index]
                next_ep = list_playlist_data[next_ep_index]
                try:
                    playlist = mpv.command('get_property', 'playlist')
                except Exception:
                    logger.info('redirect_next_ep: mpv exception found, exit')
                    return
                ne_url = next_ep['stream_url']
                cu_url = ep['stream_url']
                cu_re_url = self.data['stream_url'] if ep['file_path'] == self.data['file_path'] \
                    else ep.get('redirect_url', '')
                cu_mpv_list = [i for i in playlist if i.get('playing')
                               and i['filename'] in (cu_url, cu_re_url)]
                if not cu_mpv_list:
                    logger.info('redirect_next_ep: mpv cur playing filename not match playlist_data, may need check')
                    # 可能是起播时，集进度超50，在未获取重定向就进入下一集了。导致 stop_sec_dict 有未完成的条目，未进入 done_list。
                    done_list.append(key)
                    continue
                cu_mpv_index = playlist.index(cu_mpv_list[0])
                if cu_mpv_index == (len(playlist) - 1):
                    return
                if playlist[cu_mpv_index + 1]['filename'] != ne_url:
                    logger.info('redirect_next_ep: mpv next filename not match playlist_data, may need check')
                    continue
                mpv_cmd = next_ep['mpv_cmd']
                if configs.check_str_match(self.data['netloc'], 'dev', 'stream_prefix', log=False):
                    stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
                    ne_re_url = get_redirect_url(ne_url.replace(stream_prefix, ''), follow_redirect=True)
                    ne_re_url = f'{stream_prefix}{ne_re_url}'
                else:
                    ne_re_url = get_redirect_url(ne_url, follow_redirect=True)
                mpv_cmd[1] = ne_re_url
                try:
                    mpv.command(*mpv_cmd)
                    mpv.command('playlist-move', len(playlist), cu_mpv_index + 1)
                    mpv.command('playlist-remove', cu_mpv_index + 2)
                except Exception:
                    logger.info('redirect_next_ep: mpv exception found, exit')
                    return
                self.playlist_data[next_ep_key]['redirect_url'] = ne_re_url
                # logger.info(f'redirect_next_ep: {next_ep_index=} {next_ep_key=}')
                logger.info(f'redirect_next_ep: {mpv_cmd}')
                done_list.append(key)
                # pprint.pprint(mpv.command('get_property', 'playlist'))
            time.sleep(5)

    def prefetch_next_ep_loop(self):
        prefetch_percent = configs.raw.getfloat('playlist', 'prefetch_percent', fallback=100)
        prefetch_type = configs.raw.get('playlist', 'prefetch_type', fallback='null')
        if prefetch_percent == 100:
            return
        if len(self.playlist_data) == 1:
            return
        prefetch_data['on'] = True
        stop_sec_dict = prefetch_data['stop_sec_dict']
        done_list = prefetch_data['done_list']
        prefetch_host = configs.raw.get('playlist', 'prefetch_host', fallback='').replace('，', ',')
        prefetch_path = configs.raw.get('playlist', 'prefetch_path', fallback='').replace('，', ',')
        prefetch_path = tuple(p.strip() for p in prefetch_path.split(',') if p.strip())
        while prefetch_data['on']:
            for key, stop_sec in stop_sec_dict.copy().items():
                ep = self.playlist_data.get(key)
                if not ep:
                    continue
                if not ep['media_path'].startswith('http'):
                    return
                if not key or not stop_sec or key in done_list:
                    continue
                if prefetch_host and not configs.check_str_match(ep['netloc'], 'playlist', 'prefetch_host',
                                                                 log_by=False) or not prefetch_host:
                    return
                if prefetch_path and not any(p in ep['file_path'] for p in prefetch_path):
                    logger.info(f'{ep["file_path"]} not contain {prefetch_path=} skip prefetch')
                    return
                total_sec = ep['total_sec']
                if total_sec == 86400:
                    if mpv := self.player_kwargs.get('mpv'):
                        try:
                            total_sec = mpv.duration or 86400
                        except Exception:
                            logger.info('prefetch_next_ep_loop: mpv exit')
                            break
                position = stop_sec / total_sec
                if position * 100 <= prefetch_percent:
                    continue
                list_playlist_data = list(self.playlist_data.values())
                if ep == list_playlist_data[-1]:
                    logger.warn('prefetch_next_ep_loop: ep == list_playlist_data[-1]')
                    break
                next_ep_index = list_playlist_data.index(ep) + 1
                ep = list_playlist_data[next_ep_index]
                if prefetch_type == 'sequence':
                    ep['gui_cmd'] = 'download_only'
                    requests_urllib('http://127.0.0.1:58000/pl', _json=ep)
                elif prefetch_type == 'first_last':
                    # if ep['total_sec'] == 86400:
                    #     # strm 媒体信息 无 -> 有：外挂字幕链接会失效。
                    #     # 持久性缓存时会禁用播放列表：获取媒体信息来加速时的第二集播放。
                    #     self.emby_thin.get_playback_info(ep['item_id'], timeout=60)
                    ep['gui_cmd'] = 'download_not_play'
                    # ep['stream_url'] = get_redirect_url(ep['stream_url'], follow_redirect=True)
                    requests_urllib('http://127.0.0.1:58000/pl', _json=ep)
                else:
                    null_file = 'NUL' if os.name == 'nt' else '/dev/null'
                    dl = Downloader(ep['stream_url'], ep['basename'], save_path=null_file, size=ep.get('size'))
                    threading.Thread(target=dl.percent_download, args=(0, 0.08), daemon=True).start()
                    threading.Thread(target=dl.percent_download, args=(0.98, 1), daemon=True).start()
                done_list.append(key)
            time.sleep(5)
        logger.info('prefetch_next_ep_loop: exit')


class PlayerManager(BaseManager, PrefetchManager):

    def playlist_add(self, eps_data=None):
        super().playlist_add(eps_data=eps_data)
        threading.Thread(target=self.prefetch_next_ep_loop, daemon=True).start()
        threading.Thread(target=self.redirect_next_ep_loop, daemon=True).start()
        threading.Thread(target=self.realtime_playing_feedback_loop, daemon=True).start()
