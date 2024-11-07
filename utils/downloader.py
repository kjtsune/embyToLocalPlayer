import os.path
import threading
import time
import typing

from utils.configs import configs, MyLogger
from utils.net_tools import requests_urllib, tg_notify
from utils.tools import load_json_file, dump_json_file, scan_cache_dir, safe_deleter

logger = MyLogger()


class Downloader:
    def __init__(self, url, _id, size=None, cache_path=None, save_path=None):
        self._id = _id
        self.url = url
        self.file = save_path or os.path.join(cache_path, _id)
        self.file_is_busy = False
        self.download_only = False
        self.cancel = False
        self.pause = False
        self.size = size or self.get_size()
        self.chunk_size = 1024 * 1024
        self.progress = 0
        if not save_path:
            os.path.exists(cache_path) or os.mkdir(cache_path)

    def get_size(self):
        response = requests_urllib(self.url, http_proxy=configs.dl_proxy, res_only=True)
        return int(response.getheader('Content-Length'))

    def range_download(self, start: int, end: int, speed=0, update=False) -> int:
        sleep = 1 / speed if speed else 0
        if start == 0:
            if safe_deleter(self.file):
                logger.info(f'delete by start 0, {self.file}')
        open_mode = 'r+b' if os.path.exists(self.file) else 'wb'
        header_start = start - 1 if start else 0
        headers = {'Range': f'bytes={header_start}-{end}'}
        try:
            response = requests_urllib(self.url, headers=headers, http_proxy=configs.dl_proxy, res_only=True)
        except Exception:
            logger.error(self._id, 'connect init error')
            return start
        logger.debug(headers)
        h_size = int(response.getheader('Content-Length'))
        logger.debug('total_size', self.size, 'size', h_size, 'size_mb', h_size // 1024 // 1024, f'{open_mode=}')
        with open(self.file, open_mode) as f:
            f.seek(header_start)
            logger.debug(f'seek {header_start=}')
            try:
                while chunk := response.read(self.chunk_size):
                    if self.cancel or self.pause:
                        return start
                    f.write(chunk)
                    if start < self.size * 0.1:
                        f.flush()
                    start += self.chunk_size
                    if update:
                        tmp_progress = start * 100 // self.size / 100
                        if tmp_progress >= self.progress:
                            self.progress = tmp_progress
                    sleep and time.sleep(sleep)
            except Exception:
                logger.error(self._id, 'internet interrupt! retry')
                return start
            # logger.info(self._id, 'part download success', download_times, 'MB')
        return end

    def percent_download(self, start, end, speed=0, update=True):
        self.file_is_busy = True
        logger.info(f'download: {self._id} _start {start} _end {end}')
        _start = int(float(self.size * start))
        _end = int(float(self.size * end))
        end_with = self.range_download(_start, _end, speed=speed, update=update)
        while end_with != _end:
            if self.cancel or self.pause:
                self.file_is_busy = False
                return
            logger.info('percent download error found')
            time.sleep(1)
            _start = end_with
            end_with = self.range_download(_start, _end, speed=speed, update=update)
        if update:
            self.progress = end
            logger.debug(self._id, end, 'done')
        self.file_is_busy = False
        return True

    def download_fist_last(self):
        self.percent_download(0, 0.01, update=False)
        self.percent_download(0.99, 1, update=False)
        self.progress = 0.01

    def cancel_download(self):
        self.cancel = True
        while self.file_is_busy:
            time.sleep(1)
        os.path.exists(self.file) and os.remove(self.file)


class DownloadManager:
    def __init__(self, cache_path, speed_limit=0):
        self.cache_path = cache_path
        self.tasks = {}
        self.db = {}
        self.db_path = configs.cache_db
        self.update_loop_lock = False
        self.speed_limit = speed_limit
        if configs.gui_is_enable:
            os.path.exists(cache_path) or os.mkdir(cache_path)
            self.load_db()
            threading.Thread(target=self.update_db_loop, daemon=True).start()
        if configs.raw.getboolean('gui', 'auto_resume', fallback=False):
            threading.Thread(target=self.resume_or_pause, kwargs={'resume_from_db': True}).start()

    def _init_dl(self, data, check_only=False):
        url, _id, pos = data['stream_url'], data['fake_name'], data['position']
        dl = self.tasks.get(_id) or Downloader(url, _id, cache_path=self.cache_path)
        download_only = True if dl.download_only or data.get('download_only') else False
        dl.download_only = download_only
        if _id not in self.tasks and _id in self.db:
            dl.progress = self.db[_id]['progress']
        if not check_only:
            self.db.update({_id: self.db_single_dict(dl) for _id, dl in self.tasks.items()})
            self.tasks[_id] = dl
        logger.debug(f'init_dl {dl.download_only=}')
        return url, _id, pos, dl

    @staticmethod
    def db_single_dict(dl):
        return dict(progress=dl.progress, download_only=dl.download_only, stream_url=dl.url)

    def download_only(self, data):
        url, _id, pos, dl = self._init_dl(data)
        if dl.progress == 1:
            logger.info(f'{_id} already done')
            return
        dl.download_only = True
        if dl.file_is_busy:
            return
        if dl.percent_download(dl.progress, 1, speed=self.speed_limit):
            dl.download_only = False

    def play_check(self, data):
        url, _id, pos, dl = self._init_dl(data, check_only=True)
        if not dl.download_only and dl.progress > pos:
            logger.info(f'play_check {dl.download_only=}')
            data['media_path'] = dl.file
        data['gui_cmd'] = 'play'
        requests_urllib('http://127.0.0.1:58000/gui', _json=data)

    def download_play(self, data, play=True):
        url, _id, pos, dl = self._init_dl(data)
        if dl.download_only:
            logger.info('download only detected, refuse play')
            return
        if dl.progress >= pos:
            if dl.progress == 0 and not dl.file_is_busy:
                dl.download_fist_last()
            if play:
                data['media_path'] = dl.file
                data['gui_cmd'] = 'play'
                requests_urllib('http://127.0.0.1:58000/dl', _json=data)
        else:
            logger.info(f'{pos=} > {dl.progress} skip play')
        if not dl.file_is_busy and dl.progress != 1:
            logger.info('start download')
            dl.percent_download(dl.progress, 1, speed=self.speed_limit)

    def delete(self, data=None, _id: typing.Union[str, list] = None):
        self.update_loop_lock = True
        if data:
            url, _id, pos, dl = self._init_dl(data)
            dl.cancel_download()
        _ids = _id if isinstance(_id, list) else [_id]
        logger.info(f'ready to delete: {_ids=}')
        for _id in _ids:
            if _id in self.tasks:
                self.tasks[_id].cancel_download()
                del self.tasks[_id]
            else:
                if safe_deleter(os.path.join(self.cache_path, _id)):
                    logger.info('delete done', _id)
        self.save_db()
        self.update_loop_lock = False

    def resume_or_pause(self, data=None, resume_from_db=False):
        def data_by_db():
            result = []
            for __id, _dict in self.db.items():
                p = _dict['progress']
                if p == 1:
                    continue
                d = dict(fake_name=__id, position=None)
                d.update(_dict)
                result.append(d)
            return result

        operate = data['operate'] if not resume_from_db else 'resume'
        data_list = data['data_list'] if not resume_from_db else data_by_db()
        logger.debug(f'{operate=}\n{data_list=}')
        for data in data_list:
            url, _id, pos, dl = self._init_dl(data)
            if operate == 'pause':
                dl.pause = True
            elif operate == 'resume':
                if dl.progress == 1:
                    continue
                elif dl.progress == 0:
                    dl.download_fist_last()
                threading.Thread(target=dl.percent_download,
                                 kwargs=dict(start=dl.progress, end=1, speed=self.speed_limit)).start()

    def cache_size_limit(self):
        limit = int(configs.raw.getint('gui', 'cache_size_limit') * 1024 ** 3)
        # i: os.DirEntry
        dir_info = scan_cache_dir()
        dir_size = sum([i['stat'].st_size for i in dir_info])
        if dir_size > limit:
            logger.info('out of cache limit')
            dir_info.sort(key=lambda i: i['stat'].st_mtime)
            self.delete(_id=dir_info[0])

    def load_db(self):
        _db = load_json_file(self.db_path, 'dict')
        cache_file = os.listdir(self.cache_path)
        self.db = {file: info for file, info in _db.items() if file in cache_file}

    def save_db(self, force=False):
        if not force:
            self.load_db()
        self.db.update({_id: self.db_single_dict(dl) for _id, dl in self.tasks.items()})
        dump_json_file(self.db, self.db_path)

    def update_db_loop(self):
        times = 0
        while True:
            if self.update_loop_lock:
                logger.info('update lock')
                time.sleep(1)
                continue
            if self.tasks:
                task_done = [_id for (_id, dl) in self.tasks.items() if dl.progress == 1 or dl.pause]
                self.save_db()
                logger.debug('update db loop')
                self.tasks = {k: v for k, v in self.tasks.items() if k not in task_done}
                times += 1
                if times > 10:
                    self.cache_size_limit()
                    times = 0
            time.sleep(3)


def prefetch_resume_tv():
    conf = configs.raw.get('dev', 'prefetch_conf', fallback='')
    if not conf:
        return
    confs = conf.replace('，', ',').replace('；', ';').split(';')
    confs = [i.strip() for i in confs if i.strip()]
    for conf in confs:
        host, user_id, api_key, *startswith = [i.strip() for i in conf.split(',') if i.strip()]
        logger.info(f'prefetch conf: {host=} {user_id=} {api_key=} {startswith=}')
        threading.Thread(target=_prefetch_resume_tv, args=(host, user_id, api_key, startswith), daemon=True).start()


def _prefetch_resume_tv(host, user_id, api_key, startswith):
    startswith = tuple(startswith)
    null_file = 'NUL' if os.name == 'nt' else '/dev/null'
    headers = {
        'accept': 'application/json',
        'X-MediaBrowser-Token': api_key,
    }
    params = {
        'Fields': 'MediaStreams,PremiereDate,Path',
        'MediaTypes': 'Video',
        'Limit': '12',
        'X-Emby-Token': api_key,
    }

    if configs.raw.getboolean('tg_notify', 'get_chat_id', fallback=False):
        tg_notify('_get_chat_id')

    item_done_stat = {}  # {item_id:[source_id,]}
    sleep_again = False
    while True:
        try:
            items = requests_urllib(f'{host}/Users/{user_id}/Items/Resume',
                                    params=params, headers=headers, get_json=True, timeout=10)
        except Exception:
            time.sleep(600)
            continue
        # dump_json_file(items, 'z_resume_emby.json')
        items = items['Items']
        items = [i for i in items if i.get('SeriesName') and i.get('PremiereDate')
                 and time.mktime(time.strptime(i['PremiereDate'][:10], '%Y-%m-%d')) > time.time() - 86400 * 7]
        resume_ids = [i['Id'] for i in items]
        item_done_stat = {k: v for k, v in item_done_stat.items() if k in resume_ids}
        fresh_item_list = []
        for ep in items:
            item_id = ep['Id']
            source_info = ep['MediaSources'][0] if 'MediaSources' in ep else ep
            file_path = source_info['Path']
            if not file_path.startswith(startswith) and '/' not in startswith:
                continue
            if item_id in item_done_stat.keys():
                if sleep_again:
                    sleep_again = False
                    continue
                else:
                    sleep_again = True
            else:
                item_done_stat[item_id] = []
                fresh_item_list.append(item_id)
            # if ep['UserData'].get('LastPlayedDate'):
            #     continue
            try:
                playback_info = requests_urllib(f'{host}/Items/{item_id}/PlaybackInfo',
                                                params=params, headers=headers, get_json=True)
                play_session_id = playback_info['PlaySessionId']

                image = f'[ ]({host}/emby/Items/{item_id}/Images/Primary?maxHeight=282&maxWidth=500)'
                item_url = f"[emby]({host}/web/index.html#!/item?id={item_id}&serverId={ep['ServerId']})"
                notify_msg = f"{image}{ep['SeriesName']} \| `{time.ctime()}` \| {item_url}"

                for source_info in playback_info['MediaSources']:
                    file_path = source_info['Path']
                    container = os.path.splitext(file_path)[-1]
                    source_id = source_info['Id']
                    if source_id in item_done_stat[item_id]:
                        continue
                    else:
                        item_done_stat[item_id].append(source_id)
                    # stream_url = f'{host}/videos/{ep["Id"]}/stream{container}' \
                    #              f'?MediaSourceId={source_info["Id"]}&Static=true&api_key={api_key}'
                    stream_url = f'{host}/emby/videos/{item_id}/stream{container}' \
                                 f'?DeviceId=embyToLocalPlayer&MediaSourceId={source_id}&Static=true' \
                                 f'&PlaySessionId={play_session_id}&api_key={api_key}'
                    if stream_redirect := configs.ini_str_split('dev', 'stream_redirect'):
                        stream_redirect = zip(stream_redirect[0::2], stream_redirect[1::2])
                        for (_raw, _jump) in stream_redirect:
                            if _raw in stream_url:
                                stream_url = stream_url.replace(_raw, _jump)
                                break
                    root_dir = os.path.dirname(os.path.dirname((os.path.dirname(file_path))))
                    relative_path = file_path.replace(root_dir, '')[1:]
                    notify_msg += f'\n`{relative_path}`'
                    if configs.raw.getboolean('tg_notify', 'disable_prefetch', fallback=False):
                        logger.info(f'tg_notify, {relative_path}')
                        continue
                    if configs.check_str_match(host, 'dev', 'stream_prefix', log=False):
                        stream_prefix = configs.ini_str_split('dev', 'stream_prefix')[0].strip('/')
                        stream_url = f'{stream_prefix}{stream_url}'
                    logger.info(f'prefetch {relative_path} \n{stream_url[:100]}')
                    dl = Downloader(url=stream_url, _id=os.path.basename(file_path), save_path=null_file)
                    try:
                        dl.percent_download(0, 0.05)
                        dl.percent_download(0.98, 1)
                    except Exception:
                        logger.error(f'prefetch error on download connection, skip\n{stream_url}')
                    print()
                if item_id in fresh_item_list:
                    tg_notify(notify_msg)
            except Exception as e:
                logger.error(f'_prefetch_resume_tv error found {str(e)[:100]}')
                break
        time.sleep(600)
