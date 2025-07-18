import typing

import requests


class EmbyApi:
    def __init__(self, host, api_key, user_id, *,
                 http_proxy=None, socks_proxy=None, cert_verify=True):
        self.host = host.rstrip('/').split('/web/index')[0]
        self.api_key = api_key
        self.user_id = user_id
        self.req = requests.Session()
        if not cert_verify:
            self.req.verify = False
            from requests.packages import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.req.headers.update({'Accept': 'application/json'})
        self.req.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                               '(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
                                 'Referer': f'{self.host}/web/index.html',
                                 'X-Emby-Authorization': f'MediaBrowser Client="EmbyApi",Token="{self.api_key}"',
                                 'Authorization': f'MediaBrowser Client="EmbyApi",Token="{self.api_key}"',
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
        params = params or {'X-Emby-Token': self.api_key}
        params.update({'X-Emby-Token': self.api_key})
        url = rf'{self.host}/emby/{path}'
        res = self.req.get(url, params=params, )
        res.raise_for_status()
        return res.json() if get_json else res

    def post(self, path, _json, params=None):
        params = params or {'X-Emby-Token': self.api_key}
        params.update({'X-Emby-Token': self.api_key})
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

    def get_episodes(self, item_id, season_id=None, get_user_data=False, get_sources=False):
        params = {'SeasonId': season_id} if season_id else {}
        if get_user_data:
            if not self.user_id:
                raise ValueError('get_user_data require user id')
            params.update({'UserId': self.user_id})
        if get_sources:
            params.update({'Fields': 'MediaSources,Path,ProviderIds'})
        res = self.get(f'Shows/{item_id}/Episodes', params=params)
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
