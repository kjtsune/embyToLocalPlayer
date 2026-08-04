import json
import os
import time

import requests


class SimklApi:

    def __init__(self, client_id, client_secret, token_file=None, oauth_code=None, http_proxy=None,
                 code_received=False, app_name='embyToLocalPlayer', app_version='1.1'):
        self.base_url = 'https://api.simkl.com'
        self.client_id = client_id
        self.client_secret = client_secret
        self.app_name = app_name
        self.app_version = app_version
        self.redirect_uri = 'http://localhost:58000/simkl_auth'
        self.req = requests.Session()
        self.req.headers.update({'Content-Type': 'application/json',
                                 'User-Agent': f'{app_name}/{app_version}'})
        if http_proxy:
            self.req.proxies = {'http': http_proxy, 'https': http_proxy}
        self.oauth_code = oauth_code
        self.access_token = {}
        self.token_file = token_file or 'simkl_token.json'
        self.code_received = code_received
        self._min_post_interval = 1.0  # simkl: post 限制每秒最多一个
        self._last_post_ts = 0
        self.init_token_workflow()

    @property
    def base_params(self):
        return {'client_id': self.client_id, 'app-name': self.app_name, 'app-version': self.app_version}

    def _respect_post_rate_limit(self):
        elapsed = time.time() - self._last_post_ts
        if elapsed < self._min_post_interval:
            time.sleep(self._min_post_interval - elapsed)

    def get(self, path, params=None):
        _params = dict(self.base_params)
        if params:
            _params.update(params)
        url = f'{self.base_url}/{path}'
        res = self.req.get(url, params=_params)
        try:
            if res.status_code == 404:
                return
            return res.json()
        except Exception:
            raise ConnectionError(f'error found, {res.status_code=} {url=}') from None

    def post(self, path, params=None, _json=None, skip_rate_limit=False):
        if not skip_rate_limit:
            self._respect_post_rate_limit()
        _params = dict(self.base_params)
        if params:
            _params.update(params)
        url = f'{self.base_url}/{path}'
        res = self.req.post(url, json=_json if _json is not None else {}, params=_params)
        self._last_post_ts = time.time()
        if res.status_code == 401 and path != 'oauth/token':
            # access_token 失效/被用户撤销，且 simkl 无 refresh_token，只能提示重新走浏览器授权
            try:
                os.remove(self.token_file)
            except Exception:
                pass
            raise PermissionError(f'error found, {res.status_code=} {url=}, require re-auth')
        try:
            return res.json()
        except Exception:
            raise PermissionError(f'error found, {res.status_code=} {url=}') from None

    def add_ep_or_movie_to_history(self, movies: list = None, shows: list = None):
        # https://api.simkl.org/api-reference/simkl/add-to-history
        # movies: [{'ids': {...}, 'title':.., 'year':..}, ..]
        # shows: [{'ids': {...}, 'title':.., 'year':.., 'seasons': [{'number':N, 'episodes':[{'number':N},..]}],
        #          'use_tvdb_anime_seasons': True}, ..]
        # simkl 对重复标记会自动跳过 (no-op by default unless ?allow_rewatch=yes)，不需要预先查重。
        body = {}
        if movies:
            body['movies'] = movies
        if shows:
            body['shows'] = shows
        if not body:
            return
        res = self.post('sync/history', _json=body)
        return res

    def test(self):
        return self.post('users/settings')

    def _open_browser(self):
        url = f'https://simkl.com/oauth/authorize?response_type=code&client_id={self.client_id}' \
              f'&redirect_uri={self.redirect_uri}&app-name={self.app_name}&app-version={self.app_version}'
        if os.name == 'nt':
            os.startfile(url)
        else:
            raise ValueError(f'simkl: auth require, open url in browser\n{url}')

    def get_access_token(self, oauth_code):
        res = self.post('oauth/token', _json={
            'code': oauth_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }, skip_rate_limit=True)
        if not res.get('access_token'):
            print('simkl: oauth_token failed, may already succeed or require new oauth_code')
            return

        res['obtained_at'] = int(time.time())  # simkl 不像 trakt 返回 created_at，自己记录换取时间用于估算过期
        with open(self.token_file, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=2)

        self.access_token = res
        self.req.headers.update({'Authorization': f'Bearer {self.access_token["access_token"]}'})
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
        obtained_at = self.access_token.get('obtained_at') or 0
        expires_in = self.access_token.get('expires_in') or 0
        expires_time = obtained_at + expires_in
        if not expires_in or expires_time > time.time() + 7 * 86400:
            self.req.headers.update({'Authorization': f'Bearer {self.access_token["access_token"]}'})
            return True

    def init_token_workflow(self):
        if self.code_received:
            self.get_access_token(oauth_code=self.oauth_code)
            return
        if self.is_token_saved() and self.is_token_work():
            return
        if not self.is_token_saved():
            if not all([self.client_id, self.client_secret]):
                raise ValueError('simkl: require client_id, client_secret')
            if not self.oauth_code or not self.access_token:
                self._open_browser()
                return
            self.get_access_token(oauth_code=self.oauth_code)
        if not self.is_token_work():
            try:
                os.remove(self.token_file)
            except Exception:
                pass
            self._open_browser()
