import socket
import time

from utils.configs import MyLogger, configs

logger = MyLogger()

class EmbyApiThin:
    hostname = socket.gethostname()
    from utils.net_tools import requests_urllib
    req = staticmethod(requests_urllib)
    from utils.tools import show_version_info
    version = show_version_info()

    def __init__(self, data=None, *, host='', api_key='', user_id='', device_id=''):

        if not data and not all([host, api_key, user_id]):
            raise ValueError('EmbyApiThin: data or host api_key required')
        self.host = host.rstrip('/').split('/web/index')[0]
        self.api_key = api_key
        self.user_id = user_id
        self.device_id = device_id
        self.is_emby = True
        data_headers = {}
        if data:
            self.host = f"{data['scheme']}://{data['netloc']}"
            self.api_key = data['api_key']
            self.user_id = data.get('user_id', '')
            self.device_id = data.get('device_id', '')
            if server := data.get('server'):
                self.is_emby = (server == 'emby')
            data_headers = data['headers']  # 应该是 jellyfin

        device_name = f'{self.hostname[:1]}***{self.hostname[-1:]}' if self.hostname else 'unknow'
        auth_str = (f'MediaBrowser Client="embyToLocalPlayer",Token="{self.api_key}",Device="{device_name}"'
                    f',DeviceId="{self.device_id}"')
        self.headers = {
            f'User-Agent': f'embyToLocalPlayer/{self.version}',
            'X-Emby-Authorization': auth_str,
            'X-Emby-Token': self.api_key,
            'Authorization': auth_str,
        }
        self.headers.update(data_headers)


    def get(self, path, params=None, get_json=True, user=False, timeout=5):
        ext_str = '/emby' if self.is_emby else ''
        if user:
            ext_str += f'/Users/{self.user_id}'
        url = f'{self.host}{ext_str}/{path}'
        res = self.req(url, params=params, get_json=get_json, headers=self.headers, timeout=timeout)
        return res

    def post(self, path, params=None, _json=None, user=False, timeout=5):
        ext_str = '/emby' if self.is_emby else ''
        if user:
            ext_str += f'/Users/{self.user_id}'
        url = f'{self.host}{ext_str}/{path}'
        res = self.req(url, params=params, _json=_json, method='POST', headers=self.headers, timeout=timeout)
        return res

    def get_playback_info(self, item_id, timeout=15):
        # emby strm 在回传时可以扫出媒体信息，应该是这个请求产生的结果的。
        res = self.get(f'Items/{item_id}/PlaybackInfo', timeout=timeout)
        return res

    def get_resume_items(self):
        params = {
            'Fields': 'MediaStreams,PremiereDate,Path',
            'MediaTypes': 'Video',
            'Limit': '12',
        }
        res = self.get(f'Items/Resume', params=params, user=True)
        return res

    def get_item(self, item_id):
        return self.get(f'Items/{item_id}', user=True)

    def get_items(self, ids, params=None):
        params = params or {}
        params.update({'Ids': ','.join(ids), })
        res = self.get(f'Items', params=params, user=True)
        return res

    def list_season_eps(self, season_id, params):
        res = self.get(f'Shows/{season_id}/Episodes', params=params)
        return res


    def update_playing(self, data):
        self.post('Sessions/Playing',
                  _json={
                      'ItemId': data['item_id'],
                      'PlaySessionId': data['play_session_id'],
                  })

    def update_stop(self, stop_sec, data):
        ticks = stop_sec * 10 ** 7
        self.post('Sessions/Playing/Stopped',
                  _json={
                      'PositionTicks': ticks,
                      'ItemId': data['item_id'],
                      'PlaySessionId': data['play_session_id'],
                  })

    def change_emby_play_position(self, stop_sec, data):
        if stop_sec > 10 * 60 * 60:
            logger.error('stop_sec error, check it')
            return
        realtime_data = data.get('realtime_data', {})  # 由实时回传功能标记
        if not realtime_data.get('start'):
            # 若省略该请求，低版本 Emby/4.8.0.64 继续观看无法新增条目，高版本 Emby 直接回传失败。
            self.update_playing(data=data)
        if not realtime_data.get('end'):
            self.update_stop(stop_sec=stop_sec, data=data)

    def realtime_playing_request_sender(self, data, cur_sec, method='playing',
                                        event='TimeUpdate', paused=False, speed=1.0):
        url_path = {
            'start': 'Sessions/Playing',
            'playing': 'Sessions/Playing/Progress',
            'end': 'Sessions/Playing/Stopped',
        }[method]
        _json = {
            'ItemId': data['item_id'],
            'MediaSourceId': data['media_source_id'],
            'PlaySessionId': data['play_session_id'],
            'PositionTicks': int(cur_sec * 10 ** 7),
            'PlayMethod': 'DirectStream',
            'CanSeek': True,
            'IsPaused': paused,
            'IsMuted': False,
            'PlaybackRate': speed,
            'QueueableMediaTypes': ['Video'],
            'RepeatMode': 'RepeatNone',
        }
        if method == 'playing':
            _json['EventName'] = event
        try:
            self.post(url_path, _json=_json, timeout=10)
            return True
        except Exception as e:
            logger.info(f'playing feedback {method} failed: {e}')
            time.sleep(5)
            return False


class LocalTalk:
    local_uri = configs.local_uri

    def __init__(self):
        from utils.net_tools import requests_urllib

        self.req = requests_urllib

    def post(self, path, data):
        url = f'{self.local_uri}/{path}'
        self.req(url, _json=data)

    def downloader(self, data):
        self.post('dl', data=data)

    def gui(self, data):
        self.post('gui', data=data)

    def playlist(self, data):
        self.post('pl', data=data)
