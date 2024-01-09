import functools
import json
import os
import time
import typing

import requests


class TraktApi:
    def __init__(self, user_id, client_id, client_secret, token_file=None, oauth_code=None, http_proxy=None):
        self.base_url = 'https://api.trakt.tv'
        self.user_id = user_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.req = requests.Session()
        self.req.headers.update({'Accept': 'application/json',
                                 'trakt-api-key': client_id,
                                 'trakt-api-version': '2', })
        if http_proxy:
            self.req.proxies = {'http': http_proxy, 'https': http_proxy}
        self.oauth_code = oauth_code
        self.access_token = {}
        self.token_file = token_file or 'trakt_token.json'
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

    @functools.lru_cache
    def get_single_season(self, _id, season_num, translations=''):
        """
        _id: Trakt ID, Trakt slug, or IMDB ID
        translations: specific 2 digit country language code
        return: [{.., ids:ep_ids}, ..] not standard ids_item, not type field
        """
        trans = f'?translations={translations}' if translations else ''
        res = self.get(f'shows/{_id}/seasons/{season_num}{trans}') or []
        return res

    @functools.lru_cache
    def id_lookup(self, provider, _id, _type: typing.Literal['movie', 'show', 'episode'] = ''):
        if _type:
            _type = '' if provider == 'imdb' else f'?type={_type}'
        allow = ['tvdb', 'tmdb', 'imdb', 'trakt']
        if provider not in allow:
            raise ValueError(f'id_type allow: {allow}')
        res = self.get(f'search/{provider}/{_id}{_type}')
        return res

    @staticmethod
    def ids_items_to_ids(ids_items):
        is_list = isinstance(ids_items, list)
        ids_items = ids_items if is_list else [ids_items]
        res = [i[i['type']]['ids'] for i in ids_items]
        return res if is_list else res[0]

    def get_watch_history(self, ids_item):
        # id_lookup -> ids_item
        # get_single_season > ep_ids :not type field
        _type = ids_item.get('type')
        path_type = f'{_type}s' if _type else ''
        # 若没指定类型，返回的记录可能有误
        path_type = path_type or 'episodes'
        trakt_id = ids_item[_type]['ids']['trakt'] if _type else ids_item['trakt']
        res = self.get(f'users/{self.user_id}/history/{path_type}/{trakt_id}')
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
            'redirect_uri': 'http://localhost/trakt',
            'grant_type': 'authorization_code'
        })
        if not res.get('access_token'):
            url = f'https://trakt.tv/oauth/authorize?client_id={self.client_id}' \
                  f'&redirect_uri=http%3A%2F%2Flocalhost%2Ftrakt&response_type=code'
            if os.name == 'nt':
                os.startfile(url)
            raise ValueError('oauth_token failed, may require new oauth_code')

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

    def init_token_workflow(self, oauth_code=None):
        oauth_code = oauth_code or self.oauth_code
        if self.is_token_saved() and self.is_token_work():
            return
        if not self.is_token_saved():
            if not all([self.user_id, self.client_id, self.client_secret]):
                raise ValueError('require user_id, client_id, client_secret')
            if not oauth_code:
                url = f'https://trakt.tv/oauth/authorize?client_id={self.client_id}' \
                      f'&redirect_uri=http%3A%2F%2Flocalhost%2Ftrakt&response_type=code'
                if os.name == 'nt':
                    os.startfile(url)
                raise ValueError('require new oauth_code')
            self.get_access_token(oauth_code=oauth_code)
        if not self.is_token_work():
            self.refresh_access_token()
