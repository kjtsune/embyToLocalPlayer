import functools
import json
import os
import time
import typing

import requests


class TraktApi:
    def __init__(self, user_id, client_id, client_secret, token_file=None, oauth_code=None, http_proxy=None,
                 code_received=False):
        self.base_url = 'https://api.trakt.tv'
        self.user_id = user_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.req = requests.Session()
        self.req.headers.update({'Accept': 'application/json',
                                 'trakt-api-key': client_id,
                                 'trakt-api-version': '2',
                                 'User-Agent': 'embyToLocalPlayer/1.1', })  # 'trakt.py (4.4.0)'
        if http_proxy:
            self.req.proxies = {'http': http_proxy, 'https': http_proxy}
        self.oauth_code = oauth_code
        self.access_token = {}
        self.token_file = token_file or 'trakt_token.json'
        self.code_received = code_received
        self.init_token_workflow()

    def get(self, path, params=None):
        url = f'{self.base_url}/{path}'
        res = self.req.get(url, params=params)
        try:
            if res.status_code == 404:
                return
            return res.json()
        except Exception:
            raise ConnectionError(f'error found, {res.status_code=} {url=}') from None

    def post(self, path, params=None, _json=None):
        url = f'{self.base_url}/{path}'
        res = self.req.post(url, json=_json, params=params)
        try:
            return res.json()
        except Exception:
            raise PermissionError(f'error found, {res.status_code=} {url=}') from None

    def ids_to_trakt_url(self, ids, _type: typing.Literal['movie', 'show'] = ''):
        _type = _type or ids.get('type')
        if not _type:
            ids_item = self.id_lookup('trakt', _id=ids['slug'])
            _type = ids_item.get('type')
        url = f"https://trakt.tv/{_type}s/{ids['slug']}"
        return url

    def get_season_watched_via_ep_ids(self, ep_ids, get_keys=False):
        # 若遇到未上映却实际看过时（个别平台提前播放），该数据会遗漏。
        # return { 'number': sea_num, 'episodes': {'number': ep_num, 'completed': Bool} }
        # get_keys return { '1-1', '1-2' ..}
        ep_ids = self.ids_to_ids_item(ep_ids)
        ser_id = ep_ids['show']['ids']['slug']
        season_num = ep_ids['episode']['season']
        show_data = self.get_show_watched_progress(ser_id)
        sea_data = [i for i in show_data['seasons'] if i['number'] == season_num]
        if not sea_data:
            return None
        sea_data = sea_data[0]
        if get_keys:
            sea_data = [f'{season_num}-{ep["number"]}' for ep in sea_data['episodes'] if ep['completed']]
        return sea_data

    def get_season_via_ep_ids(self, ep_ids, info_only=False, get_key_map=False):
        # get_key_map => {f'{sea_num}-{ep_num}': ep_ids, '1-2': ep_ids, ..}
        ep_ids = self.ids_to_ids_item(ep_ids)
        ser_id = ep_ids['show']['ids']['slug']
        season_num = ep_ids['episode']['season']
        res = self.get_series_single_season(ser_id=ser_id, season_num=season_num, info_only=info_only)
        if get_key_map:
            if info_only:
                raise ValueError('get_key_map require disable info_only')
            map_dict = {f'{season_num}-{ep["number"]}': ep['ids'] for ep in res}
            return map_dict
        return res

    @functools.lru_cache
    def get_series_single_season(self, ser_id, season_num, translations='', info_only=False):
        """
        ser_id: Trakt ID, Trakt slug, or IMDB ID
        translations: specific 2 digit country language code
        return: [{.., ids:ep_ids}, ..] not standard ids_item, not type field
        """
        trans = f'?translations={translations}' if translations and not info_only else ''
        if info_only:
            trans = '/info'
        res = self.get(f'shows/{ser_id}/seasons/{season_num}{trans}') or []
        return res

    @functools.lru_cache
    def id_lookup(self, provider, _id, _type: typing.Literal['movie', 'show', 'episode'] = ''):
        # 碰到通过 imdb id 查询若网络报错 500，可以用 tmdb id 查就正常。
        # 报错 500 时用官方库 trakt.py Trakt['search'].lookup(_id, 'imdb') 查询一遍后，该 imdb id 再次查询也不报错了，原因未知。
        api_suf = f'?type={_type}' if _type and provider != 'imdb' else ''
        if _type == 'movie' and provider == 'tvdb':
            # tvdb 无法指定 type=movie 可能匹配错误，未核实是否一定返回电视剧。
            api_suf = ''
        allow = ['tvdb', 'tmdb', 'imdb', 'trakt']
        if provider not in allow:
            raise ValueError(f'id_type allow: {allow}')
        res = self.get(f'search/{provider}/{_id}{api_suf}')
        if res :
            _res = res[0]
            res_type = _res['type']
            if  _type == 'episode' and provider == 'imdb':
                # imdb 不能指定类型，集数的 imdb id 只能查到主条目，而不是分集。
                if res_type != 'episode' : # 可能返回 show 类型，而不是 episode。
                    # print('trakt_api: id_lookup fail, cuz ep lookup not support imdb, require trakt id')
                    return []
            if _type == 'movie' and provider == 'tvdb':
                if res_type != 'movie' :
                    return []
        return res

    def ids_to_ids_item(self, ids):
        if 'show' not in ids and 'movie' not in ids:
            provider = 'imdb' if ids.get('imdb') else 'trakt'
            ids = self.id_lookup(provider=provider, _id=ids[provider])[0]
        return ids

    @staticmethod
    def ids_items_to_ids(ids_items):
        is_list = isinstance(ids_items, list)
        ids_items = ids_items if is_list else [ids_items]
        res = [i[i['type']]['ids'] for i in ids_items]
        return res if is_list else res[0]

    def get_watch_history(self, ids_item, _type: typing.Literal['show', 'movie', 'episode'] = None) -> list:
        # id_lookup -> ids_item
        # get_single_season > ep_ids :not type field
        # return 观看动作相关的历史列表。剧集无法判断是否完成观看。
        _type = ids_item.get('type') or _type
        path_type = f'{_type}s' if _type else ''
        # 若没指定类型，返回的记录可能有误
        path_type = path_type or 'episodes'
        trakt_id = ids_item[_type]['ids']['trakt'] if ids_item.get(_type) else ids_item['trakt']
        res = self.get(f'users/{self.user_id}/history/{path_type}/{trakt_id}')
        return res

    def get_watched_data(self, _type: typing.Literal['movies', 'shows'] = 'shows'):
        res = self.get(f'sync/watched/{_type}')
        return res

    def get_playback_progress(self):
        # 应该是精确到分钟的
        res = self.get('sync/playback')
        return res

    def get_show_watched_progress(self, _id):
        # Trakt ID, Trakt slug, or IMDB ID
        # 含有 aired 的数据，重置的 api 需要 vip
        res = self.get(f'shows/{_id}/progress/watched')
        return res

    def check_is_watched(self, ids_item, _type: typing.Literal['show', 'movie', 'episode'] = None):
        # id_lookup -> ids_item
        _type = ids_item.get('type') or _type
        if _type in ['movie', 'episode']:
            res = self.get_watch_history(ids_item, _type=_type)
            return res
        if not _type:
            raise ValueError('ids not contain type, input it manually')
        trakt_id = ids_item[_type]['ids']['trakt'] if ids_item.get(_type) else ids_item['trakt']
        res = self.get_show_watched_progress(trakt_id)
        aired, completed = res['aired'], res['completed']
        # 不严谨，分季情况未区分。
        if completed >= aired:
            return res

    def add_ep_or_movie_to_history(self, ids_items, watched_at=''):
        # id_lookup -> ids_item
        # get_single_season > ep_ids :not type field
        ids_items = ids_items if isinstance(ids_items, list) else [ids_items]
        _json = {
            'movies': [],
            'episodes': []
        }
        for item in ids_items:
            _type = item.get('type')
            ids = item[_type]['ids'] if _type else item
            _type = _type or 'episode'
            obj = {'ids': ids}
            if watched_at:
                obj['watched_at'] = watched_at
            _json[f'{_type}s'].append(obj)
        res = self.post('sync/history', _json=_json)
        return res

    def test(self):
        self.get(f'calendars/my/dvd/2000-01-01/1')

    def receive_oauth_code(self):
        url = f'https://trakt.tv/oauth/authorize?client_id={self.client_id}' \
              f'&redirect_uri=http%3A%2F%2Flocalhost%2Ftrakt&response_type=code'
        if os.name == 'nt':
            os.startfile(url)

    def get_access_token(self, oauth_code):
        res = self.post('oauth/token', _json={
            'code': oauth_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': 'http://localhost:58000/trakt_auth',
            'grant_type': 'authorization_code'
        })
        if not res.get('access_token'):
            print('trakt: oauth_token failed, may already succeed or require new oauth_code')
            return

        with open(self.token_file, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=2)

        self.access_token = res
        return res

    def refresh_access_token(self):
        if not self.access_token.get('refresh_token'):
            raise ValueError('refresh_token not found')
        res = self.post('oauth/token', _json={
            'refresh_token': self.access_token['refresh_token'],
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': 'http://localhost/trakt',
            'grant_type': "refresh_token"
        })
        if not res.get('access_token'):
            os.remove(self.token_file)
            raise ValueError('refresh_token incorrect, remove token file')

        self.access_token = res
        self.req.headers.update({'Authorization': f'Bearer {self.access_token["access_token"]}'})
        with open(self.token_file, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=2)
        return res

    def is_token_saved(self):
        try:
            with open(self.token_file, encoding='utf-8') as f:
                self.access_token = json.load(f)
                return True
        except Exception:
            return False

    def is_token_work(self):
        if not self.access_token.get('access_token'):
            return
        expires_time = self.access_token['created_at'] + self.access_token['expires_in']
        if expires_time > time.time() + 7 * 86400:
            self.req.headers.update({'Authorization': f'Bearer {self.access_token["access_token"]}'})
            return True

    def _open_browser(self):
        url = f'https://trakt.tv/oauth/authorize?client_id={self.client_id}' \
              f'&redirect_uri=http://localhost:58000/trakt_auth&response_type=code'
        if os.name == 'nt':
            os.startfile(url)
        else:
            raise ValueError(f'trakt: auth require, open url in browser\n{url}')

    def init_token_workflow(self):
        if self.code_received:
            self.get_access_token(oauth_code=self.oauth_code)
            return
        if self.is_token_saved() and self.is_token_work():
            return
        if not self.is_token_saved():
            if not all([self.user_id, self.client_id, self.client_secret]):
                raise ValueError('require user_id, client_id, client_secret')
            if not self.oauth_code or not self.access_token:
                self._open_browser()
                return
            self.get_access_token(oauth_code=self.oauth_code)
        if not self.is_token_work():
            self.refresh_access_token()
