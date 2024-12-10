import datetime
import difflib
import functools
import os
import typing

import requests


class BangumiApi:
    def __init__(self, username=None, access_token=None, private=True, http_proxy=None):
        self.host = 'https://api.bgm.tv/v0'
        self.username = username
        self.access_token = access_token
        self.private = private
        self.http_proxy = http_proxy
        self.req = requests.Session()
        self._req_not_auth = requests.Session()
        self.init()

    def init(self):
        for r in self.req, self._req_not_auth:
            r.headers.update({'Accept': 'application/json', 'User-Agent': 'kjtsune/embyBangumi'})
            if self.access_token:
                r.headers.update({'Authorization': f'Bearer {self.access_token}'})
            if self.http_proxy:
                r.proxies = {'http': self.http_proxy, 'https': self.http_proxy}
        self._req_not_auth.headers = {k: v for k, v in self._req_not_auth.headers.items() if k != 'Authorization'}

    def get(self, path, params=None):
        res = self.req.get(f'{self.host}/{path}',
                           params=params)
        return res

    def post(self, path, _json, params=None):
        res = self.req.post(f'{self.host}/{path}',
                            json=_json, params=params)
        return res

    def put(self, path, _json, params=None):
        res = self.req.put(f'{self.host}/{path}',
                           json=_json, params=params)
        return res

    def patch(self, path, _json, params=None):
        res = self.req.patch(f'{self.host}/{path}',
                             json=_json, params=params)
        return res

    def get_me(self):
        res = self.get('me')
        if 400 <= res.status_code < 500:
            if os.name == 'nt':
                os.startfile('https://next.bgm.tv/demo/access-token')
            raise ValueError('BangumiApi: Unauthorized, access_token may wrong')
        return res.json()

    @functools.lru_cache
    def search(self, title, start_date, end_date, limit=5, list_only=True):
        title = title.replace('-', '')
        res = self._req_not_auth.post(f'{self.host}/search/subjects',
                                      json={'keyword': title,
                                            'filter': {'type': [2],
                                                       'air_date': [f'>={start_date}',
                                                                    f'<{end_date}'],
                                                       'nsfw': True}},
                                      params={'limit': limit}, )
        res = res.json()
        return res['data'] if list_only else res

    @functools.lru_cache
    def search_old(self, title, list_only=True):
        res = self.req.get(f'{self.host[:-2]}/search/subject/{title}', params={'type': 2, 'responseGroup': 'large'})
        try:
            res = res.json()
        except Exception:
            res = {'results': 0, 'list': []}
        return res['list'] if list_only else res

    @functools.lru_cache
    def get_subject(self, subject_id):
        res = self.get(f'subjects/{subject_id}')
        return res.json()

    @functools.lru_cache
    def get_related_subjects(self, subject_id):
        res = self.get(f'subjects/{subject_id}/subjects')
        return res.json()

    @functools.lru_cache
    def get_episodes(self, subject_id, _type=0):
        res = self.get('episodes', params={
            'subject_id': subject_id,
            'type': _type,
        })
        return res.json()

    def get_target_season_episode_id(self, subject_id, target_season: int, target_ep: typing.Union[int, list] = None):
        season_num = 1
        current_id = subject_id
        ep_num_list = target_ep if isinstance(target_ep, list) else None
        target_ep = ep_num_list[0] if isinstance(target_ep, list) else target_ep

        if target_season > 5 or (target_ep and target_ep > 99):
            return None, None if target_ep else None

        if target_season == 1:
            if not target_ep:
                return current_id
            fist_part = True
            while True:
                if not fist_part:
                    current_info = self.get_subject(current_id)
                    if current_info['platform'] not in ('TV', 'WEB'):
                        break
                episodes = self.get_episodes(current_id)
                ep_info = episodes['data']
                _target_ep = [i for i in ep_info if i['sort'] == target_ep]
                if _target_ep:
                    if ep_num_list:
                        return current_id, [i['id'] for i in ep_info if i['sort'] in ep_num_list]
                    return current_id, _target_ep[0]['id']
                normal_season = True if episodes['total'] > 3 and ep_info[0]['sort'] <= 1 else False
                if not fist_part and normal_season:
                    break
                related = self.get_related_subjects(current_id)
                next_id = [i for i in related if i['relation'] == '续集']
                if not next_id:
                    break
                current_id = next_id[0]['id']
                fist_part = False
            return None, None if target_ep else None

        while True:
            related = self.get_related_subjects(current_id)
            next_id = [i for i in related if i['relation'] == '续集']
            remake = [i for i in related if i['relation'] == '不同演绎']
            next_id = next_id or remake
            if not next_id:
                break
            current_id = next_id[0]['id']
            current_info = self.get_subject(current_id)
            if current_info['platform'] != 'TV':
                continue
            episodes = self.get_episodes(current_id)
            ep_info = episodes['data']
            normal_season = True if episodes['total'] > 3 and ep_info[0]['sort'] <= 1 else False
            _target_ep = [i for i in ep_info if i['sort'] == target_ep]
            ep_found = True if target_ep and _target_ep else False
            if normal_season:
                season_num += 1
            if season_num > target_season:
                break
            if season_num == target_season:
                if not target_ep:
                    return current_id
                if not ep_found:
                    continue
                if ep_num_list:
                    return current_id, [i['id'] for i in ep_info if i['sort'] in ep_num_list]
                return current_id, _target_ep[0]['id']
        return None, None if target_ep else None

    def get_subject_collection(self, subject_id, get_eps=False):
        extra = '/episodes' if get_eps else ''
        user = '-' if get_eps else self.username
        res = self.get(f'users/{user}/collections/{subject_id}{extra}')
        if res.status_code == 404:
            return {}
        return res.json()

    def get_user_eps_collection(self, subject_id, map_state=False):
        # map_state=true return { ep_num: {'watched': bool, 'id': ep_id}}
        eps = self.get_subject_collection(subject_id, get_eps=True)
        if not map_state:
            return eps
        eps = eps['data']
        # ep['episode']['ep'] 会导致分批放送匹配失败。
        # ep['episode']['ep'] == 0 是 SP，会造成 sort 重复，故排除
        state = {ep['episode']['sort']: {'watched': bool(ep['type'] == 2), 'id': ep['episode']['id']} for ep in eps
                 if ep['episode']['ep'] != 0}
        return state

    def mark_episode_watched(self, subject_id, ep_id):
        data = self.get_subject_collection(subject_id)
        if data.get('type') == 2:
            return
        if not data:
            self.add_collection_subject(subject_id=subject_id)
        if isinstance(ep_id, list):
            self.change_episode_state(ep_id=ep_id, subject_id=subject_id)
        else:
            self.change_episode_state(ep_id=ep_id, state=2)

    def add_collection_subject(self, subject_id, private=None, state=3):
        private = self.private if private is None else private
        self.post(f'users/-/collections/{subject_id}',
                  _json={'type': state,
                         'private': bool(private)})

    def change_episode_state(self, ep_id, state=2, subject_id=None):
        if isinstance(ep_id, list):
            if not subject_id:
                raise ValueError('update eps require subject_id')
            res = self.patch(f'users/-/collections/{subject_id}/episodes',
                             _json={
                                 'episode_id': ep_id,
                                 'type': 2
                             })
        else:
            res = self.put(f'users/-/collections/-/episodes/{ep_id}',
                           _json={'type': state})
        if 333 < res.status_code < 444:
            raise ValueError(f'{res.status_code=} {res.text}')
        return res


class BangumiApiEmbyVer(BangumiApi):
    @staticmethod
    def _emby_filter(bgm_data):
        # 旧 api 由返回数据内容受到大小参数的影响。
        # common_keys = ['id', 'name', 'name_cn', 'summary', 'rating', 'collection', 'images']
        # v0_subject_unique_keys = ['type', 'nsfw', 'locked', 'date', 'platform', 'series', 'infobox', 'volumes',
        #                           'total_episodes', 'meta_tags', 'tags']
        # legacy_subject_small_unique_keys = ['url', 'type', 'air_date', 'air_weekday', 'eps', 'eps_count', 'rank']
        update_date = str(datetime.date.today())
        return_list = isinstance(bgm_data, list)
        bgm_data = bgm_data if return_list else [bgm_data]
        is_v0 = bool(bgm_data[0].get('date'))

        common_key = ['id', 'name', 'name_cn']
        useful_key = common_key + ['date', 'score', 'rank']
        v0_key_map = common_key + ['date', ('rating', 'score'), ('rating', 'rank')]
        legacy_key_map = common_key + ['air_date', ('rating', 'score'), 'rank']
        key_map = v0_key_map if is_v0 else legacy_key_map

        res = []
        for data in bgm_data:
            d = {}
            for (k, m) in zip(useful_key, key_map):
                if isinstance(m, str):
                    d[k] = data[m]
                    continue
                v = data  # data.copy() 会更稳妥。
                for _m in m:
                    v = v[_m]
                d[k] = v
            d['update_date'] = update_date
            d['is_v0'] = is_v0
            res.append(d)
        return res if return_list else res[0]

    def emby_search(self, title, ori_title, premiere_date: str, is_movie=False):
        # 新 api 通过 _emby_filter() => {is_v0 : True} 判断
        air_date = datetime.datetime.fromisoformat(premiere_date[:10])
        start_date = air_date - datetime.timedelta(days=2)
        end_date = air_date + datetime.timedelta(days=2)
        bgm_data = None
        if ori_title:
            bgm_data = self.search(title=ori_title, start_date=start_date, end_date=end_date)
        bgm_data = bgm_data or self.search(title=title, start_date=start_date, end_date=end_date)
        if not bgm_data and is_movie:
            title = ori_title or title
            end_date = air_date + datetime.timedelta(days=200)
            bgm_data = self.search(title=title, start_date=start_date, end_date=end_date)
        if not bgm_data or (bgm_data and self.title_diff_ratio(
                title=title, ori_title=ori_title, bgm_data=bgm_data[0]) < 0.5):
            # use_old_api = True
            for t in ori_title, title:
                bgm_data = self.search_old(title=t)
                if bgm_data and self.title_diff_ratio(title, ori_title, bgm_data=bgm_data[0]) > 0.5:
                    break
            else:
                bgm_data = None
        if not bgm_data:
            return
        return self._emby_filter(bgm_data=bgm_data)

    @staticmethod
    def title_diff_ratio(title, ori_title, bgm_data):
        ori_title = ori_title or title
        ratio = max(difflib.SequenceMatcher(None, bgm_data['name'], ori_title).quick_ratio(),
                    difflib.SequenceMatcher(None, bgm_data['name_cn'], title).quick_ratio(),
                    difflib.SequenceMatcher(None, bgm_data['name'], title).quick_ratio())
        return ratio
