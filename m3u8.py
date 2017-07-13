# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import requests
import urllib.parse
import urllib.request
import os, json, shutil
import time

DIR = 'tmp'
RETRY = 3

class Downloader:
    def __init__(self, pool_size, retry=RETRY):
        self.session = self._get_http_session(pool_size, pool_size, retry)
        self.retry = retry
        self.dir = ''
        self.succed = {}
        self.failed = []
        self.ts_total = 0

    def _get_http_session(self, pool_connections, pool_maxsize, max_retries):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=max_retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

    def run(self, m3u8_url, dir='tmp'):
        self.dir = dir
        uri_list = []
        if self.dir and not os.path.isdir(self.dir):
            os.makedirs(self.dir)

        r = self.session.get(m3u8_url, timeout=10)
        if r.ok:
            body = r.content.decode("utf-8")
            if body:
                print(body)
                for n in body.split('\n'):
                    if n and n.startswith("#EXT-X-MEDIA:"):
                        uri = n.split("URI=")
                        _uri = uri[-1]
                        uri_list.append(urllib.parse.urljoin(m3u8_url, _uri[1:-1].strip()))
                print(uri_list)
                if len(uri_list):
                    for k in uri_list:
                        response = self.session.get(k, timeout=10)
                        if response.ok:
                            body = response.content.decode("utf-8")
                            if body:
                                ts_list = [urllib.parse.urljoin(k, n.strip()) for n in body.split('\n') if n and not n.startswith("#")]
                                if ts_list:
                                    for j in ts_list:
                                        self.download(j, self.dir)
                else:
                    ts_list = [urllib.parse.urljoin(m3u8_url, n.strip()) for n in body.split('\n') if
                               n and not n.startswith("#")]
                    if ts_list:
                        for j in ts_list:
                            self.download(j, self.dir)
        else:
            print(r.status_code)

    def download(self, url, path):
        print(url)
        base_url, origin_name = os.path.split(url)
        save_path = os.path.join(path, origin_name)
        response = urllib.request.urlretrieve(url=url)
        contents = open(response[0], "br").read()

        # save path
        f = open(save_path, "wb")
        f.write(contents)
        f.close()


class Parser:
    def __init__(self, dir=DIR):
        self.dir = dir
        self.retry = 0
        if self.dir and not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def prase(self, http_url, type):
        response = requests.get(url=http_url, verify=False)
        if response.status_code == 200:
            jsondata = json.loads(response.content.decode('utf-8'))

            if type == "VIDEO":
                playlist = jsondata["playlist"]
                for k in playlist["videos"]:
                    self.download(k["uri"])
                    self.download(k["thumbnail"])
                    self.download(k["download_uri"])
            elif type == "PHOTO":
                playlist = jsondata["album"]
                for k in playlist["photos"]:
                    self.download(k["uri"])
                    self.download(k["thumbnail"])
            # if os.path.exists(self.dir):
            #     shutil.rmtree(self.dir)  # delete local temp files
            # print("end")
        else:
            print("http error %d" % response.status_code)
            self.prase(http_url, type)

    def download(self, http_link):
        self.retry = 0
        self.dir = DIR

        path = urllib.parse.urlparse(http_link).path[1:]
        _dir = os.path.split(path)[0]
        name, ext = os.path.splitext(path)
        self.dir = os.path.join(self.dir, _dir)
        print(self.dir)
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)
        if ext == ".m3u8":
            self._download(http_link, self.dir)

            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=RETRY)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            r = session.get(http_link, timeout=10)
            if r.ok:
                uri_list = []
                body = r.content.decode("utf-8")
                if body:
                    for n in body.split('\n'):
                        if n and n.startswith("#EXT-X-MEDIA:"):
                            uri = n.split("URI=")
                            if len(uri):
                                _uri = uri[-1]
                                uri_list.append(urllib.parse.urljoin(http_link, _uri[1:-1].strip()))
                    if len(uri_list):
                        for k in uri_list:
                            self.download(k)
                    else:
                        ts_list = [urllib.parse.urljoin(http_link, n.strip()) for n in body.split('\n') if
                                   n and not n.startswith("#")]
                        if ts_list:
                            for j in ts_list:
                                self._download(j, self.dir)
            else:
                print("Parse %s failed %d" % (http_link, r.status_code))
        else:
            self._download(http_link, self.dir)

    def _download(self, http_link, dst):
        origin_name = os.path.split(http_link)[1]
        save_path = os.path.join(dst, origin_name)
        print(http_link, save_path)
        if os.path.exists(save_path):
            print(save_path + " exist.")
            return
        try:
            _http_link = urllib.parse.quote(http_link, safe=':/')  # parse link to url
            response = urllib.request.urlretrieve(url=_http_link)
            contents = open(response[0], "br").read()
            with open(save_path, 'wb') as f:
                f.write(contents)
                f.close()
        except Exception as e:
            print('Network(%s) conditions is not good.Reloading.' % str(e))
            if self.retry < RETRY:
                self.retry += 1
                if os.path.exists(save_path):
                    os.remove(save_path)
                self._download(http_link, save_path)
            else:
                print("Retry %d times faild" % self.retry)
                return

if __name__ == '__main__':
    # parse = Parser()
    # parse.prase(http_url="https://api.kandaovr.com/video/v1/playlist?codec=4&container=H&language=ZH-CN&name=KANDAO_APP_MAIN&vbr=8&warping=C", type="VIDEO")
    # parse.prase(http_url="http://cms.kandaovr.com/video/v1/playlist?codec=5&warping=O&container=H&vbr=4&name=KANDAO_APP_MAIN", type="VIDEO")
    # parse.prase(http_url="https://api.kandaovr.com/photo/v1/album?language=EN-US&name=KANDAO_APP_MAIN", type="PHOTO")
    # parse.prase(http_url="https://api.kandaovr.com/photo/v1/album?language=EN-US&name=KANDAO_APP_MAIN", type="PHOTO")
    downloader = Downloader(50)
    downloader.run("http://v3.kandaovr.com/H264/8M/temple_4kx4k_360x180_cube_lr.m3u8", 'tmp2')
