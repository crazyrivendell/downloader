# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from http import client
import os
import logging
import time
import re
import urllib.request
import urllib.parse
from urllib.parse import urlparse
from html.parser import HTMLParser

log = logging.getLogger()
log.setLevel(level=logging.DEBUG)
fileLogFormatter = logging.Formatter(
    "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
fileHandler = logging.FileHandler("log.log")
fileHandler.setFormatter(fileLogFormatter)
fileHandler.setLevel(logging.INFO)
log.addHandler(fileHandler)

consoleLogFormat = logging.Formatter(
    "%(asctime)s %(levelname)1.1s %(filename)5.5s %(lineno)3.3s-> %(message)s")
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(consoleLogFormat)
consoleHandler.setLevel(logging.DEBUG)
log.addHandler(consoleHandler)

Retry = 3


class HtmlParser(HTMLParser):
    def __init__(self, output_list=None):
        HTMLParser.__init__(self)
        if output_list is None:
            self.output_list = []
        else:
            self.output_list = output_list

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.output_list.append(dict(attrs).get('href'))
        if tag == 'img' or tag == 'script':
            self.output_list.append(dict(attrs).get('src'))


class JsonParser:
    def __init__(self, output_list=None):
        if output_list is None:
            self.output_list = []
        else:
            self.output_list = output_list

    def feed(self, data):
        self.output_list.extend(re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", data, re.I|re.L))


class HlsPraser:
    def __init__(self, http_link):
        self.link = http_link
        self.output_list = []

    def feed(self, data):
        if data:
            for n in data.split('\n'):
                if n and n.startswith("#EXT-X-MEDIA:"):
                    uri = n.split("URI=")
                    if len(uri):
                        _uri = uri[-1]
                        self.output_list.append(urllib.parse.urljoin(self.link, _uri[1:-1].strip()))

            self.output_list.extend([urllib.parse.urljoin(self.link, m.strip()) for m in data.split('\n') if m and not m.startswith("#")])

def progress_callback(a, b, c):
    """
    :param a:  number of download blocks
    :param b:  size of a block
    :param c:  total size of the download file
    :return:
    """
    per = 100.0 * a * b / c
    if per > 100:
        per = 100
    # print('%.2f%%' % per)


class Downloader:
    def __init__(self, link, dst_dir="temp"):
        self.link = link
        self.retry = Retry
        self.dir = dst_dir
        self.links = list()
        self.success = list()
        self.failure = list()
        self.id = 0

        self.links.append(self.link)
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def get_current_time(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def url_check(self, url):
        _url = urllib.parse.urlparse(url)
        conn = client.HTTPConnection(_url.netloc)
        conn.request("HEAD", _url.path)
        if conn.getresponse():
            return True
        else:
            return False

    def download(self, http_link):
        url = urlparse(http_link)
        save_path = os.path.join(self.dir, url.netloc, url.path[1:] if url.path.startswith("/") else url.path)
        log.info("http_link=%s path=%s" % (http_link, save_path))
        dir = os.path.dirname(save_path)
        log.info("dir=%s" % dir)
        if not os.path.exists(dir):
            os.makedirs(dir)
        if save_path.endswith("/"):
            save_path = os.path.join(save_path, "file")
        try:
            _http_link = urllib.parse.quote(http_link, safe=':/?&=')  # parse link to url
            data, headers = urllib.request.urlretrieve(url=_http_link, filename=save_path, reporthook=progress_callback)
            log.info("http_link=%s save_path=%s" % (_http_link, save_path))

            if headers["Content-Type"] == "text/html":
                p = HtmlParser()
                p.feed(open(data, "br").read().decode('utf-8'))
                self.links.extend(urllib.parse.urljoin(http_link, url) for url in p.output_list)
            elif headers["Content-Type"] == "application/json":
                p = JsonParser()
                p.feed(open(data, "br").read().decode('utf-8'))
                self.links.extend(urllib.parse.urljoin(http_link, url) for url in p.output_list)
            else:
                log.info("Content-Type %s" % headers["Content-Type"])

            filename = os.path.basename(save_path)
            ext = os.path.splitext(filename)[1]
            if ext == ".m3u8":
                p = HlsPraser(http_link=http_link)
                p.feed(open(data, "br").read().decode('utf-8'))
                self.links.extend(urllib.parse.urljoin(http_link, url) for url in p.output_list)
                log.info(self.links)
            self.success.append(http_link)
            self.retry = Retry
        except Exception as e:
            log.info('Network(%s) conditions is not good.Reloading.' % str(e))
            if self.retry:
                self.retry -= 1
                if os.path.exists(save_path):
                    os.remove(save_path)
                self.download(http_link)
            else:
                print("Retry %d times faild" % Retry)
                self.failure.append(http_link)
        self.id += 1
        log.info(self.id)
        if self.id < len(self.links):
            self.download(self.links[self.id])


    def run(self):
        log.info("start")
        if self.url_check(self.link):
            self.download(self.link)
            log.info("download failure: %s" % self.failure)


if __name__ == "__main__":
    # downloader1 = Downloader("https://kandaovr.com", dst_dir="website")
    # downloader1.run()
    # downloader2 = Downloader("https://api.kandaovr.com/video/v1/playlist?codec=5&warping=O&container=H&vbr=4&name=KANDAO_APP_MAIN", dst_dir="api")
    # downloader2.run()
    # downloader3 = Downloader("https://v1.kandaovr.com/offcenter/H265/4M/temple1080p_3dv_offcenter.m3u8", dst_dir="m3u8")
    # downloader3.run()
    downloader4 = Downloader("http://v3.kandaovr.com/H264/8M/huizhou_4kx4k_360x180_cube_lr.m3u8", dst_dir="m3u8")
    downloader4.run()
