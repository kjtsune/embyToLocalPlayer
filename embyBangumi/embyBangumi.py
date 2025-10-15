import datetime
import difflib
import json
import os.path
import pprint
import re
import signal
import sys
from configparser import ConfigParser
from functools import wraps

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from utils.emby_api import EmbyApi
    from utils.bangumi_api import BangumiApiEmbyVer
    from utils.configs import configs as etlp_config
except Exception:
    pass


def protect_write(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        received_signal = None

        def handle_signal(signum, frame):
            nonlocal received_signal
            print(f"Received signal {signum}, deferring until after write.")
            received_signal = signum

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, handle_signal)

        try:
            result = func(*args, **kwargs)
        except Exception as e:
            print(f"Error during file write: {e}")
            raise
        finally:
            if received_signal is not None:
                print(f"Re-sending signal {received_signal} to self.")
                os.kill(os.getpid(), received_signal)

        return result

    return wrapper


class Configs:
    def __init__(self):
        self.cwd = os.path.dirname(__file__)
        self.path = [os.path.join(self.cwd, 'embyBangumi' + ext) for ext in (
            f'-dev.ini', '-test.ini', '_config.ini')]
        self.path = [i for i in self.path if os.path.exists(i)][0]
        print(self.path)
        self.raw = ConfigParser()
        self.raw.read(self.path, encoding='utf-8-sig')

    def get(self, key, fallback=''):
        return self.raw.get('emby', key, fallback=fallback).strip()

    def get_int(self, key, fallback=0):
        return self.raw.getint('emby', key, fallback=fallback)


class JsonDataBase:
    def __init__(self, name, prefix='', db_type='dict', workdir=None):
        self.file_name = f'{prefix}_{name}.json' if prefix else f'{name}.json'
        self.file_path = os.path.join(workdir, self.file_name) if workdir else self.file_name
        self.db_type = db_type
        self.data = self.load()

    def load(self, encoding='utf-8'):
        try:
            with open(self.file_path, encoding=encoding) as f:
                _json = json.load(f)
        except FileNotFoundError:
            print(f'{self.file_name} not exist, return {self.db_type}')
            return dict(list=[], dict={})[self.db_type]
        else:
            return _json

    @protect_write
    def dump(self, obj, encoding='utf-8'):
        # print('saving')
        # time.sleep(1)
        with open(self.file_path, 'w', encoding=encoding) as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        # print('save done')

    def save(self):
        self.dump(self.data)


class TmdbBgmDataBase(JsonDataBase):
    def __getitem__(self, tmdb_id):
        data = self.data.get(tmdb_id)
        if not data:
            return
        air_date = datetime.date.fromisoformat(data['date'])
        today = datetime.date.today()
        if air_date + datetime.timedelta(days=90) > today:
            expire_day = 3
        elif air_date + datetime.timedelta(days=365) > today:
            expire_day = 30
        else:
            expire_day = 120
        update_date = datetime.date.fromisoformat(data['update_date'])
        if update_date + datetime.timedelta(days=expire_day) < today:
            return
        return data

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def clean_not_trust_data(self, expire_days=7, min_trust=0.5):
        expire_days = datetime.timedelta(days=expire_days)
        today = datetime.date.today()
        self.data = {_id: info for _id, info in self.data.items()
                     if info['trust'] >= min_trust or
                     datetime.date.fromisoformat(info['update_date']) + expire_days > today}
        self.save()

    def recount_trust_score(self):
        res = {}
        for _id, info in self.data.items():
            trust = max(difflib.SequenceMatcher(None, info['name'], info['emby_ori']).quick_ratio(),
                        difflib.SequenceMatcher(None, info['name_cn'], info['emby_name']).quick_ratio(),
                        difflib.SequenceMatcher(None, info['name'], info['emby_name']).quick_ratio())
            info['trust'] = trust
            res[_id] = info
        self.data = res
        self.save()


class NotResultDataBase(JsonDataBase):
    def __delitem__(self, key):
        del self.data[key]

    def is_not_result(self, tmdb_id):
        day_str = self.data.get(tmdb_id)
        if not day_str:
            return False
        expire_date = datetime.date.fromisoformat(day_str) + datetime.timedelta(days=7)
        if expire_date > datetime.date.today():
            return True
        else:
            del (self.data[tmdb_id])
            return False

    def update_status(self, tmdb_id):
        self.data[tmdb_id] = str(datetime.date.today())


def update_critic_rating_by_bgm(emby: EmbyApi, bgm: BangumiApiEmbyVer, genre='', types='Movie,Series,Video',
                                lib_name='', req_limit=50,
                                item_limit=100, start_index=0, dry_run=True):
    if not genre and not lib_name:
        print('not library_name and not genre, check ini settings')
        return

    lib_names = [i.strip() for i in lib_name.split(',') if i]
    parent_ids = [emby.get_library_id(lib_name) for lib_name in lib_names]
    tmdb_db = TmdbBgmDataBase('tmdb_bgm')
    # tmdb_db.clean_not_trust_data()
    # tmdb_db.clean_not_trust_data(expire_days=0, min_trust=0.5)
    # tmdb_db.recount_trust_score()
    # return
    not_result_db = NotResultDataBase('tmdb_bgm_not_result')
    tmdb_list = []
    req_count = 0
    item_count = 0
    not_res_log = []

    for item in emby.yield_all_items(genre=genre, types=types,
                                     fields=','.join([
                                         'PremiereDate',
                                         'ProviderIds',
                                         'CommunityRating',
                                         'CriticRating',
                                         'OriginalTitle',
                                     ]),
                                     start_index=start_index,
                                     parent_id=parent_ids):

        if req_count >= req_limit or item_count >= item_limit:
            break

        tmdb_id = item['ProviderIds']['Tmdb']
        is_movie = False if item['Type'] == 'Series' else True
        if tmdb_id in tmdb_list:
            continue
        else:
            tmdb_list.append(tmdb_id)

        # if is_movie:
        #     continue
        emby_name = item['Name']
        emby_ori = item.get('OriginalTitle', '')
        print(emby_name, end=' ')
        item_count += 1

        debug_title = '东离剑游记'
        if emby_name == debug_title:
            if tmdb_db[tmdb_id]:
                del tmdb_db[tmdb_id]
            if not_result_db.is_not_result(tmdb_id=tmdb_id):
                del not_result_db[tmdb_id]

        # emby.refresh(item['Id'])
        # continue
        re_split = re.compile(r'[／/]')
        if re_split.search(emby_ori):
            emby_ori = re_split.split(emby_ori)
            for _t in emby_ori:
                if any((bool(0x3040 <= ord(i) <= 0x30FF)) for i in _t):
                    emby_ori = _t
                    break
            else:
                emby_ori = emby_ori[0]
        premiere_date = item.get('PremiereDate')
        if not premiere_date:
            print('not PremiereDate, skip')
            continue

        if not_result_db.is_not_result(tmdb_id=tmdb_id):
            log = f' {premiere_date[:10]}\n^^^ not result ^^^\n'
            print(log)
            not_res_log.append((emby_name, premiere_date[:10]))
            continue

        bgm_old = tmdb_db[tmdb_id]
        bgm_data = bgm_old or bgm.emby_search(title=emby_name, ori_title=emby_ori, premiere_date=premiere_date,
                                              is_movie=is_movie)
        req_count = req_count if bgm_old else req_count + 2
        if not bgm_data:
            not_result_db.update_status(tmdb_id=tmdb_id)
            log = f' {premiere_date[:10]}\n^^^ not result ^^^\n'
            print(log)
            not_res_log.append((emby_name, premiere_date[:10]))
            continue

        bgm_data = bgm_data if bgm_old else bgm_data[0]
        if not bgm_old:
            bgm_data['emby_ori'] = emby_ori
            bgm_data['emby_name'] = emby_name
            bgm_data['premiere_date'] = premiere_date
            tmdb_db[tmdb_id] = bgm_data
        if not dry_run:
            emby.update_critic_rating(item['Id'], bgm_data['score'] * 10)
        print(f">>>> {bgm_data['name_cn']}[{bgm_data['name']}] {bgm_data['score']}")
        if req_count and req_count % 50 == 0:
            not_result_db.save()
            tmdb_db.save()
    if req_count > 0:
        not_result_db.save()
        tmdb_db.save()

    if not_res_log:
        print(f'\n{len(not_res_log)=}')
        pprint.pprint(not_res_log)
    print(f'\napi.bgm.tv requests count {req_count}')
    emby_total_count = sum(emby.get_items(genre=genre, types=types,
                                          parent_id=pid, start_index=start_index)['TotalRecordCount']
                           for pid in parent_ids)
    print('emby items count', emby_total_count)
    print(f'tmdb_bgm.json count {len(tmdb_db.data)}\n')
    if dry_run:
        print(f'Nothing update because of {dry_run=}')
    else:
        print(f'Total update count {item_count}')


def main():
    conf = Configs()
    http_proxy = conf.get('http_proxy', '') or None
    if etlp_emby := conf.get('etlp_emby', ''):
        my_emby = etlp_config.get_server_api_by_ini(etlp_emby, use_thin_api=False)
    else:
        my_emby = EmbyApi(
            host=conf.get('host').split('/web/index')[0],
            api_key=conf.get('api_key'),
            user_id=conf.get('user_id'),
            http_proxy=http_proxy
        )
    my_bgm = BangumiApiEmbyVer(http_proxy=http_proxy)
    update_critic_rating_by_bgm(
        emby=my_emby,
        bgm=my_bgm,
        genre=conf.get('genre', ''),
        lib_name=conf.get('library_name', ''),
        types=conf.get('types').strip(',').strip('，'),
        req_limit=conf.get_int('req_limit', 50),
        item_limit=conf.get_int('item_limit', 999),
        start_index=conf.get_int('start_index', 0),
        dry_run=conf.raw.getboolean('emby', 'dry_run', fallback=True)
    )


if __name__ == '__main__':
    main()
