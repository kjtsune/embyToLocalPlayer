import datetime
import difflib
import enum
import functools
import os
import typing

import requests


class MyIntEnum(enum.IntEnum):
    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


class SubjectState(MyIntEnum):  # Subject['type']
    WISH = 1  # 想看
    WATCHED = 2  # 看过
    WATCHING = 3  # 在看
    ON_HOLD = 4  # 搁置
    DROPPED = 5  # 抛弃


class SubjectType(MyIntEnum):  # Subject['subject_type']
    BOOK = 1  # 书籍
    ANIME = 2  # 动画
    MUSIC = 3  # 音乐
    GAME = 4  # 游戏
    REAL = 6  # 三次元

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
    def search_old(self, title, start_date, end_date, list_only=True):
        res = self.req.get(f'{self.host[:-2]}/search/subject/{title}', params={'type': 2, 'responseGroup': 'large'})
        _res = {'results': 0, 'list': []}
        try:
            res = res.json()
        except Exception:
            res = _res
        try:
            raw_list = res['list']
            # 无结果 res 也可能返回 {'list': None, 'results': 1}
            if raw_list is None:
                raise KeyError
        except KeyError: # 404 不存在时
            res = _res
            raw_list = res['list']

        res_list = []
        if isinstance(start_date, str):
            start_date = datetime.datetime.fromisoformat(start_date[:10])
            end_date = datetime.datetime.fromisoformat(end_date[:10])
        for data in raw_list:
            air_date = data['air_date'][:10]
            if air_date == '0000-00-00':
                continue
            air_date = datetime.datetime.fromisoformat(air_date)
            if start_date<= air_date <= end_date:
                res_list.append(data)
        res = {'results': len(res_list), 'list': res_list}
        return res_list if list_only else res

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

    @staticmethod
    def episodes_date_filter(episodes, dates, fuzzy_days=2):
        res = []
        date_idx = 0
        if isinstance(dates[0], str):
            dates = [datetime.datetime.fromisoformat(i[:10]) for i in dates]
        dates.sort()
        for ep in episodes['data']:
            bgm_date = ep.get('airdate') or ep.get('date')
            if not bgm_date:
                continue
            # bgm 少部分 date 是 '1999-9-20'
            if abs((datetime.datetime.strptime(bgm_date[:10], '%Y-%m-%d') - dates[date_idx]).days) <= fuzzy_days:
                res.append(ep)
                date_idx += 1
            if date_idx == len(dates):
                break
        if len(res) != len(dates):
            res = []
        return res

    def get_episodes_and_date_filter(self, subject_id, dates=None, fuzzy_days=2):
        episodes = self.get_episodes(subject_id)
        if not dates:
            return episodes, None
        filter_res = self.episodes_date_filter(episodes, dates, fuzzy_days=fuzzy_days)
        return episodes, filter_res

    def get_target_season_episode_id(self, subject_id, target_season: int, target_ep: typing.Union[int, list] = None,
                                     subject_platform=None, match_by_dates: typing.Optional[list] = None):
        season_num = 1
        current_id = subject_id
        ep_num_list = target_ep if isinstance(target_ep, list) else None
        target_ep = ep_num_list[0] if isinstance(target_ep, list) else target_ep

        if target_season > 5 or (target_ep and target_ep > 99):
            return None, None if target_ep else None
        platform_allow = ['TV']
        if not subject_platform:
            subject_platform = self.get_subject(subject_id)['platform']
        if subject_platform == 'WEB':  # 仅限主条目是 WEB 时，续集可以是 WEB。好像有主条目 TV，需要过滤掉续集里 WEB 的情况。
            platform_allow.append(subject_platform)

        custom_get_episodes = lambda _id: self.get_episodes_and_date_filter(_id, dates=match_by_dates)
        if target_season == 1:
            if not target_ep:
                return current_id
            fist_part = True
            while True:
                # if not fist_part:
                #     current_info = self.get_subject(current_id)
                #     if current_info['platform'] not in platform_allow: # TV 的续集可能是 OVA，导致匹配失败
                #         break
                episodes, match_dates_success = custom_get_episodes(current_id)
                if match_dates_success:
                    if ep_num_list:
                        return current_id, [i['id'] for i in match_dates_success]
                    return current_id, match_dates_success[0]['id']
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
            if current_info['platform'] != subject_platform:
                continue
            episodes, match_dates_success = custom_get_episodes(current_id)
            if match_dates_success:
                if ep_num_list:
                    return current_id, [i['id'] for i in match_dates_success]
                return current_id, match_dates_success[0]['id']
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

    def get_user_collections(self, username=None, subject_type=SubjectType.ANIME, state=SubjectState.WATCHING,
                             limit=50, offset=0):
        username = username or self.username
        params = {
            'subject_type': subject_type,
            'type': state,
            'limit': limit,
            'offset': offset
        }
        res = self.get(f'users/{username}/collections', params=params)
        return res.json()


    def get_subject_collection(self, subject_id, get_eps=False):
        extra = '/episodes' if get_eps else ''
        user = '-' if get_eps else self.username
        res = self.get(f'users/{user}/collections/{subject_id}{extra}')
        if res.status_code == 404:
            return {}
        return res.json()

    def list_watching_is_done_subjects(self, mark_watched=False):
        watching = self.get_user_collections()
        result = []
        for item in watching.get('data', []):
            subject = item.get('subject', {})
            if item.get('ep_status') == subject.get('eps'):
                name_cn = subject.get('name_cn') or subject.get('name')
                subject_id = subject.get('id')
                result.append((name_cn, subject_id))
                if mark_watched:
                    self.add_collection_subject(subject_id=subject_id, state=SubjectState.WATCHED)
        return result

    def get_user_eps_collection(self, subject_id, map_state=False):
        # map_state=true return { ep_num: {'watched': bool, 'id': ep_id}}
        eps = self.get_subject_collection(subject_id, get_eps=True)
        if not map_state:
            return eps
        eps = eps['data']
        # ep['episode']['ep'] 会导致分批放送匹配失败。
        # ep['episode']['ep'] == 0 是 SP，会造成 sort 重复，故排除
        state = {ep['episode']['sort']: {'watched': bool(ep['type'] == 2), 'id': ep['episode']['id'],
                                         'date': (ep['episode'].get('date') or ep['episode'].get('airdate'))}
                 for ep in eps if ep['episode']['ep'] != 0}
        return state

    def mark_episode_watched(self, subject_id, ep_id):
        data = self.get_subject_collection(subject_id)
        if data.get('type') == 2:
            return
        if not data or data.get('type') in (1, 4):
            self.add_collection_subject(subject_id=subject_id)
        if isinstance(ep_id, list):
            self.change_episode_state(ep_id=ep_id, subject_id=subject_id)
        else:
            self.change_episode_state(ep_id=ep_id, state=SubjectState.WATCHED)

    def add_collection_subject(self, subject_id, private=None, state=SubjectState.WATCHING):
        private = self.private if private is None else private
        self.post(f'users/-/collections/{subject_id}',
                  _json={'type': state,
                         'private': bool(private)})

    def change_episode_state(self, ep_id, state=SubjectState.WATCHED, subject_id=None):
        if isinstance(ep_id, list):
            if not subject_id:
                raise ValueError('update eps require subject_id')
            res = self.patch(f'users/-/collections/{subject_id}/episodes',
                             _json={
                                 'episode_id': ep_id,
                                 'type': state
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
        # 旧 api 没有 platform，此时 platform 会设置为 None
        if not bgm_data:
            return bgm_data
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
        useful_key = common_key + ['date', 'score', 'rank', 'platform']  # 返回的字典键

        v0_key_map = common_key + ['date', ('rating', 'score'), ('rating', 'rank'), 'platform']
        legacy_key_map = common_key + ['air_date', ('rating', 'score'), 'rank', 'platform']
        key_map = v0_key_map if is_v0 else legacy_key_map

        res = []
        for data in bgm_data:
            d = {}
            for (k, m) in zip(useful_key, key_map):
                if isinstance(m, str):
                    d[k] = data.get(m)
                    continue
                v = data  # data.copy() 会更稳妥。
                for _m in m:
                    v = v.get(_m, {})
                d[k] = v
            d['update_date'] = update_date
            d['is_v0'] = is_v0
            res.append(d)
        res = [i for i in res if i.get('rank') is not None and i.get('score') is not None] # 无 'rank' 为未上映，过滤掉
        return res if return_list else res[0]

    def emby_search(self, title, ori_title, premiere_date: str, is_movie=False, _tv_fuzzy_date_retry=False):
        # 新 api 通过 _emby_filter() => {is_v0 : True} 判断
        day_delta = 15 if _tv_fuzzy_date_retry else 2
        air_date = datetime.datetime.fromisoformat(premiere_date[:10])
        start_date = air_date - datetime.timedelta(days=day_delta)
        end_date = air_date + datetime.timedelta(days=day_delta)
        trust_score = 0.9 if _tv_fuzzy_date_retry else 0.5
        bgm_data = None
        for t in (ori_title, title):
            bgm_data = self.search(title=t, start_date=start_date, end_date=end_date)
            if bgm_data and self.title_diff_ratio(title, ori_title, bgm_data=bgm_data[0]) > trust_score:
                break
            else:
                bgm_data = None
        if not bgm_data and is_movie:
            end_date = air_date + datetime.timedelta(days=200)
            bgm_data = self.search(title=(ori_title or title), start_date=start_date, end_date=end_date)
            if self.title_diff_ratio(title, ori_title, bgm_data=bgm_data[0]) < trust_score:
                bgm_data = None
        if not bgm_data:
            # use_old_api = True
            for t in ori_title, title:
                bgm_data = self.search_old(title=t, start_date=start_date, end_date=end_date)
                if bgm_data and self.title_diff_ratio(title, ori_title, bgm_data=bgm_data[0]) > trust_score:
                    break
                else:
                    bgm_data = None
            else:
                if not is_movie and not _tv_fuzzy_date_retry:
                    bgm_data = self.emby_search(title, ori_title, premiere_date, _tv_fuzzy_date_retry=True)
                else:
                    bgm_data = None
        if _tv_fuzzy_date_retry:
            return bgm_data
        bgm_data = self._emby_filter(bgm_data=bgm_data)
        if not bgm_data:
            return
        return bgm_data

    @staticmethod
    def title_diff_ratio(title, ori_title, bgm_data):
        ori_title = ori_title or title
        ratio = max(difflib.SequenceMatcher(None, bgm_data['name'], ori_title).quick_ratio(),
                    difflib.SequenceMatcher(None, bgm_data['name_cn'], title).quick_ratio(),
                    difflib.SequenceMatcher(None, bgm_data['name'], title).quick_ratio())
        return ratio
