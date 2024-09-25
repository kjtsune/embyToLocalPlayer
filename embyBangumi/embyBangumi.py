import datetime
import difflib
import json
import os.path
import re
import sys
from configparser import ConfigParser

import requests

try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from utils.emby_api import EmbyApi
except Exception:
    pass


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


class BangumiApi:
    def __init__(self, http_proxy=None):
        self.host = 'https://api.bgm.tv/v0/'
        self.req = requests.Session()
        self.req.headers.update({'Accept': 'application/json',
                                 'Connection': 'keep-alive',
                                 'User-Agent': 'kjtsune/embyBangumi'})
        if http_proxy:
            self.req.proxies = {'http': http_proxy, 'https': http_proxy}

    def post(self, path, _json, params=None):
        res = self.req.post(f'{self.host.rstrip("/")}/{path.lstrip("/")}',
                            json=_json, params=params)
        return res

    def search(self, title, start_date, end_date, limit=5):
        res = self.post('search/subjects',
                        _json={"keyword": title,
                               "filter": {"type": [2],
                                          "air_date": [f'>={start_date}',
                                                       f'<{end_date}'],
                                          "nsfw": True}},
                        params=dict(limit=limit))
        return res.json()


class BangumiApiEmbyVer(BangumiApi):
    @staticmethod
    def _emby_filter(bgm_data):
        useful_key = ['date', 'id', 'name', 'name_cn', 'rank', 'score', ]
        update_date = str(datetime.date.today())
        if isinstance(bgm_data, list):
            res = []
            for data in bgm_data:
                d = {k: v for k, v in data.items() if k in useful_key}
                d['update_date'] = update_date
                res.append(d)
            return res
        else:
            d = {k: v for k, v in bgm_data.items() if k in useful_key}
            d['update_date'] = update_date
            return d

    def emby_search(self, title, premiere_date: str, is_movie=False):
        air_date = datetime.datetime.fromisoformat(premiere_date[:10])
        start_date = air_date - datetime.timedelta(days=2)
        day_after = 200 if is_movie else 2
        end_date = air_date + datetime.timedelta(days=day_after)
        bgm_data = self.search(title=title, start_date=start_date, end_date=end_date)
        return self._emby_filter(bgm_data['data'])


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

    def dump(self, obj, encoding='utf-8'):
        with open(self.file_path, 'w', encoding=encoding) as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)

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

    parent_id = emby.get_library_id(lib_name)
    tmdb_db = TmdbBgmDataBase('tmdb_bgm')
    tmdb_db.clean_not_trust_data()
    # tmdb_db.clean_not_trust_data(expire_days=0, min_trust=0.5)
    # tmdb_db.recount_trust_score()
    # return
    not_result_db = NotResultDataBase('tmdb_bgm_not_result')
    tmdb_list = []
    req_count = 0
    item_count = 0

    for item in emby.yield_all_items(genre=genre, types=types,
                                     fields=','.join([
                                         'PremiereDate',
                                         'ProviderIds',
                                         'CommunityRating',
                                         'CriticRating',
                                         'OriginalTitle',
                                     ]),
                                     start_index=start_index,
                                     parent_id=parent_id):

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
        title = emby_ori or emby_name
        premiere_date = item.get('PremiereDate')
        if not premiere_date:
            print('not PremiereDate, skip')
            continue

        if not_result_db.is_not_result(tmdb_id=tmdb_id):
            print('\n^^^ not result ^^^\n')
            continue

        bgm_old = tmdb_db[tmdb_id]
        bgm_data = bgm_old or bgm.emby_search(title=title, premiere_date=premiere_date)
        req_count = req_count if bgm_old else req_count + 1
        if emby_ori and not bgm_data:
            bgm_data = bgm.emby_search(title=emby_name, premiere_date=premiere_date)
            req_count += 1
            print(f' | {emby_ori} :not result', end=' | ')
            if not bgm_data:
                print(f'{emby_name} :not result', end=' | ')
                if is_movie:
                    print(f'{emby_ori} :try without premiere_date', end=' | ')
                    bgm_data = bgm.emby_search(title=emby_ori, premiere_date=premiere_date, is_movie=True)
                    bgm_data or print(f'{emby_name} :try without premiere_date', end=' | ')
                    req_count = req_count + 1 if bgm_data else req_count + 2
                    bgm_data = bgm_data or bgm.emby_search(title=emby_name, premiere_date=premiere_date, is_movie=True)
                if not bgm_data:
                    not_result_db.update_status(tmdb_id=tmdb_id)
                    print('\n^^^ not result ^^^\n')
        if not bgm_data:
            continue

        bgm_data = bgm_data if bgm_old else bgm_data[0]
        trust = bgm_data.get('trust') or max(difflib.SequenceMatcher(None, bgm_data['name'], emby_ori).quick_ratio(),
                                             difflib.SequenceMatcher(None, bgm_data['name_cn'],
                                                                     emby_name).quick_ratio(),
                                             difflib.SequenceMatcher(None, bgm_data['name'], emby_name).quick_ratio())
        if not bgm_old:
            bgm_data['emby_ori'] = emby_ori
            bgm_data['emby_name'] = emby_name
            bgm_data['premiere_date'] = premiere_date
            bgm_data['trust'] = trust
            tmdb_db[tmdb_id] = bgm_data
        if trust < 0.5:
            print('\n^^^ trust < 0.5 ^^^\n')
            continue
        if not dry_run:
            emby.update_critic_rating(item['Id'], bgm_data['score'] * 10)
        print(f">>>> {bgm_data['name_cn']}[{bgm_data['name']}] {bgm_data['score']}")
        if req_count % 50 == 0:
            not_result_db.save()
            tmdb_db.save()
    if req_count > 0:
        not_result_db.save()
        tmdb_db.save()

    print(f'\napi.bgm.tv requests count {req_count}')
    res = emby.get_items(genre=genre, types=types, parent_id=parent_id, start_index=start_index)
    print('emby items count', res['TotalRecordCount'])
    print(f'tmdb_bgm.json count {len(tmdb_db.data)}\n')
    if dry_run:
        print(f'Nothing update because of {dry_run=}')
    else:
        print(f'Total update count {item_count}')


def main():
    conf = Configs()
    http_proxy = conf.get('http_proxy', '') or None
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
