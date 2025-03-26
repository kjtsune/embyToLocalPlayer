class EmbyApiThin:
    def __init__(self, data, *, host='', api_key='', user_id=''):
        from utils.net_tools import requests_urllib

        self.req = requests_urllib
        if not data and not all([host, api_key, user_id]):
            raise ValueError('EmbyApiThin: data or host api_key required')
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.user_id = user_id
        if data:
            self.host = f"{data['scheme']}://{data['netloc']}"
            self.api_key = data['api_key']
            self.user_id = data['user_id']
        self.headers = {
            'Referer': f'{self.host}/web/index.html',
            'X-Emby-Authorization': f'MediaBrowser Client="embyToLocalPlayer",Token="{self.api_key}"',
            'Authorization': f'MediaBrowser Client="embyToLocalPlayer",Token="{self.api_key}"',
        }

    def get(self, path, params=None, get_json=True):
        params = params or {'X-Emby-Token': self.api_key}
        params.update(
            {
                'X-Emby-Token': self.api_key,
                'Authorization': f'MediaBrowser Client="EmbyApi",Token="{self.api_key}"',
            }
        )
        url = rf'{self.host}/emby/{path}'
        timeout = 10 if 'PlaybackInfo' in path else 5 # Jellyfin strm 获取速度慢
        res = self.req(url, params=params, get_json=get_json, headers=self.headers, timeout=timeout)
        return res

    def get_playback_info(self, item_id):
        # emby strm 在回传时可以扫出媒体信息，应该是这个请求产生的结果的。
        res = self.get(f'Items/{item_id}/PlaybackInfo')
        return res
