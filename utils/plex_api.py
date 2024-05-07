import typing

import requests


class PlexApi:
    def __init__(self, host, api_key, *,
                 http_proxy=None, socks_proxy=None, cert_verify=True):
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.req = requests.Session()
        if not cert_verify:
            self.req.verify = False
            from requests.packages import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.req.headers.update({'Accept': 'application/json'})
        self.req.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                               '(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
                                 'Referer': f'{self.host}/web/index.html',
                                 'X-Plex-Token': api_key
                                 })
        if http_proxy:
            self.req.proxies = {'http': http_proxy, 'https': http_proxy}
        if socks_proxy:
            self.req.proxies = {'http': socks_proxy, 'https': socks_proxy}

    def get(self, path, params=None):
        url = rf'{self.host}/{path}'
        return self.req.get(
            url,
            params=params,
        )

    def get_metadata(self, rating_key) -> typing.Union[dict, list]:
        res = self.get(f'library/metadata/{rating_key}')
        res = res.json()['MediaContainer']['Metadata']
        if len(res) == 1:
            return res[0]
        return res
