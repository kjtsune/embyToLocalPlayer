import socket
import typing

import requests


class EmbyApi:
    hostname = socket.gethostname()
    version = 'unknow'
    try:
        from utils.tools import show_version_info
        version = show_version_info()
    except Exception:
        pass

    def __init__(self, host, api_key, user_id, *,
                 http_proxy=None, socks_proxy=None, cert_verify=True,
                 data=None, device_id=''):
        self.host = host.rstrip('/').split('/web/index')[0]
        self.api_key = api_key
        self.user_id = user_id
        self.device_id = device_id
        self.is_emby = True
        self.req = requests.Session()
        if not cert_verify:
            self.req.verify = False
            from requests.packages import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if data:
            self.host = f"{data['scheme']}://{data['netloc']}"
            self.api_key = data['api_key']
            self.user_id = data.get('user_id', '')
            self.device_id = data.get('device_id', '')
            if server := data.get('server'):
                self.is_emby = (server == 'emby')

        device_name = f'{self.hostname[:1]}***{self.hostname[-1:]}' if self.hostname else 'unknow'
        auth_str = (f'MediaBrowser Client="embyToLocalPlayer",Token="{self.api_key}",Device="{device_name}"'
                    f',DeviceId="{self.device_id}"')
        self.req.headers.update({f'User-Agent': f'embyToLocalPlayer/{self.version}',
                                 'X-Emby-Authorization': auth_str,
                                 'X-Emby-Token': self.api_key,
                                 'Authorization': auth_str,
                                 'Accept': 'application/json',
                                 })
        self._default_fields = ','.join([
            'PremiereDate',
            'ProviderIds',
            'CommunityRating',
            'CriticRating',
            'OriginalTitle',
            'Path',
        ])
        if http_proxy:
            self.req.proxies = {'http': http_proxy, 'https': http_proxy}
        if socks_proxy:
            self.req.proxies = {'http': socks_proxy, 'https': socks_proxy}
        self.system_info = None
        self.server_id = None

    def get(self, path, params=None, get_json=True) -> typing.Union[dict, list, requests.Response]:
        url = rf'{self.host}/emby/{path}'
        res = self.req.get(url, params=params, )
        res.raise_for_status()
        return res.json() if get_json else res

    def post(self, path, _json, params=None):
        url = rf'{self.host}/emby/{path}'
        return self.req.post(
            url,
            json=_json,
            params=params,
        )

    def get_genre_id(self, name):
        try:
            res = self.get(f'Genres/{name}')['Id']
        except Exception:
            raise KeyError(f'Genres: {name} not exists, check it') from None
        return res

    def get_library_id(self, name='', get_all=False):
        if not name and not get_all:
            return
        res = self.get(f'Library/VirtualFolders')
        if get_all:
            lib_dict = {i['Name']: i['ItemId'] for i in res}
            return lib_dict
        lib_id = [i['ItemId'] for i in res if i['Name'] == name]
        if not lib_id:
            raise KeyError(f'library: {name} not exists, check it')
        return lib_id[0] if lib_id else None

    def get_seasons(self, item_id):
        res = self.get(f'Shows/{item_id}/Seasons')
        return res

    # 可能会有副作用，建议调用前先判断非管理员和高版本
    @staticmethod
    def flat_multi_ver_source_episodes(episodes):
        old = episodes
        episodes = old['Items']
        for _ in episodes:
            _['MediaSources'].sort(key=lambda x: x['Type'] != 'Default')  # 低版本的好像没这个值，但不影响

        def fill_miss_eps_item(episodes_data):
            # 4.9以上的非管理员缺少多版本条目，所以需要扁平化多版本。
            # 扁平化后判断体积时长等最好从 MediaSources 里判断，不然可能有误。

            id_set = set()
            flat_eps = []
            for ep in episodes_data:
                ep_id = ep['Id']
                ep_so = ep['MediaSources']
                df_so = ep_so[0]
                if ep_id not in id_set:
                    new_item = ep.copy()
                    new_item['MediaSources'] = [df_so]
                    id_set.add(ep_id)
                    flat_eps.append(new_item)
                if len(ep_so) == 1:
                    continue
                base_path = ep['Path']
                base_tag = df_so['Name']
                path_prefix, path_suffix = base_path.rsplit(base_tag, 1)
                for so in ep_so[1:]:
                    so_id = so['ItemId']
                    if so_id in id_set:
                        continue
                    new_item = ep.copy()
                    if so['IsRemote']:
                        new_path = f'{path_prefix}{so["Name"]}{path_suffix}'
                        new_item['Path'] = new_path
                    else:
                        new_item['Path'] = so['Path']
                    new_item['MediaSources'] = [so]
                    new_item['Id'] = so_id
                    new_item['Size'] = so['Size']
                    id_set.add(so_id)
                    flat_eps.append(new_item)
            return flat_eps

        episodes = fill_miss_eps_item(episodes)
        old['Items'] = episodes
        return old

    def get_episodes(self, item_id, season_id=None, get_user_data=False, get_sources=False, flat_multi_ver=False):
        params = {'SeasonId': season_id} if season_id else {}
        if get_user_data:
            if not self.user_id:
                raise ValueError('get_user_data require user id')
            params.update({'UserId': self.user_id})
        if get_sources:
            params.update({'Fields': 'MediaSources,Path,ProviderIds,AlternateMediaSources'})
        res = self.get(f'Shows/{item_id}/Episodes', params=params)
        if get_sources and flat_multi_ver:
            res = self.flat_multi_ver_source_episodes(res)
        return res

    def get_playback_info(self, item_id):
        res = self.get(f'Items/{item_id}/PlaybackInfo')
        return res

    def get_item(self, item_id):
        if self.user_id:
            res = self.get(f'Users/{self.user_id}/Items/{item_id}')
            return res

        ext_fields = ','.join([
            'Genres'
        ])
        fields = self._default_fields + ',' + ext_fields
        ext_params = {
            'HasTmdbId': None,
            'IncludeItemTypes': None,
            'Fields': fields,
            'X-Emby-Token': self.api_key,
        }
        res = self.get_items(ids=[item_id], ext_params=ext_params)['Items'][0]
        return res

    def get_items(self, genre='', types='Movie,Series,Video', fields: typing.Union[list, str] = None, start_index=0,
                  ids: typing.Union[list, str] = None, limit=50, parent_id=None,
                  sort_by='DateCreated,SortName',
                  recursive=True, ext_params: dict = None, filters=None, by_user=False):
        # 注意默认不包含 Episode。同时 Episode 需要 ext_params={'HasTmdbId': None}。IncludeItemTypes = None
        fields = fields or self._default_fields
        fields = fields if isinstance(fields, str) else ','.join(fields)
        params = {
            'HasTmdbId': True,
            'SortBy': sort_by,
            'SortOrder': 'Descending',
            'IncludeItemTypes': types,
            'Recursive': recursive,
            'Fields': fields,
            'StartIndex': start_index,
            'Limit': limit,
            'X-Emby-Token': self.api_key,
        }

        if genre:
            params.update({'GenreIds': self.get_genre_id(genre)})
        if ids:
            params.update({'HasTmdbId': None,
                           'IncludeItemTypes': None})
            if isinstance(ids, (list, tuple)):
                ids = map(str, ids)
                ids = ','.join(ids)
            params.update({'Ids': ids})
        if parent_id:
            params.update({'ParentId': parent_id})
        if filters:
            params.update({'Filters': filters})
            if 'IsFavorite' in filters and not by_user:
                raise ValueError('IsFavorite require by_user')
        if ext_params:
            params.update(ext_params)
        path = f'Users/{self.user_id}/Items' if by_user else 'Items'
        if by_user and not self.user_id:
            raise ValueError('user_id required')
        res = self.get(path, params=params)
        return res

    def yield_all_items(self, genre='', types='Movie,Series,Video', fields: typing.Union[list, str] = None,
                        start_index=0, piece=200, item_limit=0, parent_id: typing.Union[list, str] = None,
                        ext_params: dict = None):
        parent_ids = parent_id if isinstance(parent_id, list) else [parent_id]
        count = 0

        for pid in parent_ids:
            local_start_index = start_index
            current_piece = piece if item_limit == 0 or item_limit >= piece else item_limit

            fist = self.get_items(
                genre=genre, types=types, fields=fields,
                start_index=local_start_index, limit=current_piece,
                parent_id=pid, ext_params=ext_params
            )
            items = fist['Items']
            total = fist['TotalRecordCount']

            for item in items:
                if item_limit != 0 and count >= item_limit:
                    return
                yield item
                count += 1

            pages = (total - local_start_index) // current_piece
            for i in range(1, pages + 1):
                local_start_index = i * current_piece + start_index
                if item_limit != 0 and count >= item_limit:
                    return
                page_items = self.get_items(
                    genre=genre, types=types, fields=fields,
                    start_index=local_start_index, limit=current_piece,
                    parent_id=pid, ext_params=ext_params
                )['Items']

                for item in page_items:
                    if item_limit != 0 and count >= item_limit:
                        return
                    yield item
                    count += 1

    def search_by_trakt(self, tk_ids: dict):
        """只能搜索主条目，集和季不行"""
        ids_param = ','.join([k + '.' + str(v) for k, v in tk_ids.items() if v and k != 'tmdb'])  # tmdb may TV or Movie
        ext_params = {'AnyProviderIdEquals': ids_param, }
        res = self.get_items(ext_params=ext_params)
        return res

    def update_critic_rating(self, item_id, rating):
        get_path = f'/Users/{self.user_id}/Items/{item_id}'
        post_path = f'Items/{item_id}'
        old = self.get(path=get_path, params={'Fields': 'ChannelMappingInfo'})

        useful_key = ['Name', 'OriginalTitle', 'Id', 'DateCreated', 'SortName', 'ForcedSortName', 'PremiereDate',
                      'OfficialRating', 'Overview', 'Taglines', 'Genres', 'CommunityRating', 'RunTimeTicks',
                      'ProductionYear', 'ProviderIds', 'People', 'Studios', 'TagItems', 'Status', 'DisplayOrder',
                      'LockedFields', 'LockData']
        _not_require_key = ['ServerId', 'Etag', 'CanDelete', 'CanDownload', 'PresentationUniqueKey', 'ExternalUrls',
                            'Path', 'FileName', 'PlayAccess', 'RemoteTrailers', 'IsFolder', 'ParentId', 'Type',
                            'GenreItems', 'LocalTrailerCount', 'UserData', 'RecursiveItemCount', 'ChildCount',
                            'DisplayPreferencesId', 'AirDays', 'PrimaryImageAspectRatio', 'ImageTags',
                            'BackdropImageTags']
        # useful_key.append('ExternalUrls') # 无法更改
        new = {k: v for k, v in old.items() if k in useful_key}
        new.update({'CriticRating': rating})
        self.post(path=post_path,
                  _json=new)

    def refresh(self, item_id):
        self.post(f'Items/{item_id}/Refresh',
                  _json={
                      'Recursive': False,
                      'MetadataRefreshMode': 'FullRefresh',
                      'ReplaceAllMetadata': False,
                  })

    def mark_item_played(self, item_id):
        self.post(f'Users/{self.user_id}/PlayedItems/{item_id}', _json=None)

    def item_id_to_url(self, item_id):
        if not self.server_id:
            self.system_info = self.get('System/Info')
            self.server_id = self.system_info['Id']
        url = f'{self.host}/web/index.html#!/item?id={item_id}&serverId={self.server_id}'
        return url

    def image_url_generate(self, item_id, img_type='poster'):
        api_map = {
            'poster': 'Primary',
            'fanart': 'Backdrop/0',
            'thumb': 'Primary',
        }
        img_type = api_map.get(img_type)
        url = f'{self.host}/emby/Items/{item_id}/Images/{img_type}'
        return url
