# coding: utf-8
from __future__ import unicode_literals

import re
import itertools

from .common import InfoExtractor
from ..compat import (
    compat_str,
    compat_parse_qs,
    compat_urllib_parse_urlparse,
)
from ..utils import (
    determine_ext,
    unified_strdate,
    try_get,
    int_or_none,
)


class RutubeIE(InfoExtractor):
    IE_NAME = 'rutube'
    IE_DESC = 'Rutube videos'
    _VALID_URL = r'https?://rutube\.ru/(?:video|(?:play/)?embed)/(?P<id>[\da-z]{32})'

    _TESTS = [{
        'url': 'http://rutube.ru/video/3eac3b4561676c17df9132a9a1e62e3e/',
        'info_dict': {
            'id': '3eac3b4561676c17df9132a9a1e62e3e',
            'ext': 'mp4',
            'title': 'Раненный кенгуру забежал в аптеку',
            'description': 'http://www.ntdtv.ru ',
            'duration': 80,
            'uploader': 'NTDRussian',
            'uploader_id': '29790',
            'upload_date': '20131016',
            'age_limit': 0,
        },
        'params': {
            # It requires ffmpeg (m3u8 download)
            'skip_download': True,
        },
    }, {
        'url': 'http://rutube.ru/play/embed/a10e53b86e8f349080f718582ce4c661',
        'only_matching': True,
    }, {
        'url': 'http://rutube.ru/embed/a10e53b86e8f349080f718582ce4c661',
        'only_matching': True,
    }, {
        'url': 'http://rutube.ru/video/3eac3b4561676c17df9132a9a1e62e3e/?pl_id=4252',
        'only_matching': True,
    }]

    @classmethod
    def suitable(cls, url):
        parts = compat_urllib_parse_urlparse(url)
        params = compat_parse_qs(parts.query)

        # see if URL without parameters is OK
        res = super(RutubeIE, cls).suitable(url)

        if params:  # we only allow pl_id parameter in the url
            res = res and 'pl_id' in params and len(params) == 1

        return res

    @staticmethod
    def _extract_urls(webpage):
        return [mobj.group('url') for mobj in re.finditer(
            r'<iframe[^>]+?src=(["\'])(?P<url>(?:https?:)?//rutube\.ru/embed/[\da-z]{32}.*?)\1',
            webpage)]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        video = self._download_json(
            'http://rutube.ru/api/video/%s/?format=json' % video_id,
            video_id, 'Downloading video JSON')

        # Some videos don't have the author field
        author = video.get('author') or {}

        options = self._download_json(
            'http://rutube.ru/api/play/options/%s/?format=json' % video_id,
            video_id, 'Downloading options JSON')

        formats = []
        for format_id, format_url in options['video_balancer'].items():
            ext = determine_ext(format_url)
            if ext == 'm3u8':
                formats.extend(self._extract_m3u8_formats(
                    format_url, video_id, 'mp4', m3u8_id=format_id, fatal=False))
            elif ext == 'f4m':
                formats.extend(self._extract_f4m_formats(
                    format_url, video_id, f4m_id=format_id, fatal=False))
            else:
                formats.append({
                    'url': format_url,
                    'format_id': format_id,
                })
        self._sort_formats(formats)

        return {
            'id': video['id'],
            'title': video['title'],
            'description': video['description'],
            'duration': video['duration'],
            'view_count': video['hits'],
            'formats': formats,
            'thumbnail': video['thumbnail_url'],
            'uploader': author.get('name'),
            'uploader_id': compat_str(author['id']) if author else None,
            'upload_date': unified_strdate(video['created_ts']),
            'age_limit': 18 if video['is_adult'] else 0,
        }


class RutubeEmbedIE(InfoExtractor):
    IE_NAME = 'rutube:embed'
    IE_DESC = 'Rutube embedded videos'
    _VALID_URL = r'https?://rutube\.ru/(?:video|play)/embed/(?P<id>[0-9]+)'

    _TESTS = [{
        'url': 'http://rutube.ru/video/embed/6722881?vk_puid37=&vk_puid38=',
        'info_dict': {
            'id': 'a10e53b86e8f349080f718582ce4c661',
            'ext': 'mp4',
            'upload_date': '20131223',
            'uploader_id': '297833',
            'description': 'Видео группы ★http://vk.com/foxkidsreset★ музей Fox Kids и Jetix<br/><br/> восстановлено и сделано в шикоформате subziro89 http://vk.com/subziro89',
            'uploader': 'subziro89 ILya',
            'title': 'Мистический городок Эйри в Индиан 5 серия озвучка subziro89',
        },
        'params': {
            'skip_download': 'Requires ffmpeg',
        },
    }, {
        'url': 'http://rutube.ru/play/embed/8083783',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        embed_id = self._match_id(url)
        webpage = self._download_webpage(url, embed_id)

        canonical_url = self._html_search_regex(
            r'<link\s+rel="canonical"\s+href="([^"]+?)"', webpage,
            'Canonical URL')
        return self.url_result(canonical_url, 'Rutube')


class RutubeChannelIE(InfoExtractor):
    IE_NAME = 'rutube:channel'
    IE_DESC = 'Rutube channels'
    _VALID_URL = r'https?://rutube\.ru/tags/video/(?P<id>\d+)'
    _TESTS = [{
        'url': 'http://rutube.ru/tags/video/1800/',
        'info_dict': {
            'id': '1800',
        },
        'playlist_mincount': 68,
    }]

    _PAGE_TEMPLATE = 'http://rutube.ru/api/tags/video/%s/?page=%s&format=json'

    def _extract_videos(self, channel_id, channel_title=None):
        entries = []
        for pagenum in itertools.count(1):
            page = self._download_json(
                self._PAGE_TEMPLATE % (channel_id, pagenum),
                channel_id, 'Downloading page %s' % pagenum)
            results = page['results']
            if not results:
                break
            entries.extend(self.url_result(result['video_url'], 'Rutube') for result in results)
            if not page['has_next']:
                break
        return self.playlist_result(entries, channel_id, channel_title)

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        channel_id = mobj.group('id')
        return self._extract_videos(channel_id)


class RutubeMovieIE(RutubeChannelIE):
    IE_NAME = 'rutube:movie'
    IE_DESC = 'Rutube movies'
    _VALID_URL = r'https?://rutube\.ru/metainfo/tv/(?P<id>\d+)'
    _TESTS = []

    _MOVIE_TEMPLATE = 'http://rutube.ru/api/metainfo/tv/%s/?format=json'
    _PAGE_TEMPLATE = 'http://rutube.ru/api/metainfo/tv/%s/video?page=%s&format=json'

    def _real_extract(self, url):
        movie_id = self._match_id(url)
        movie = self._download_json(
            self._MOVIE_TEMPLATE % movie_id, movie_id,
            'Downloading movie JSON')
        movie_name = movie['name']
        return self._extract_videos(movie_id, movie_name)


class RutubePersonIE(RutubeChannelIE):
    IE_NAME = 'rutube:person'
    IE_DESC = 'Rutube person videos'
    _VALID_URL = r'https?://rutube\.ru/video/person/(?P<id>\d+)'
    _TESTS = [{
        'url': 'http://rutube.ru/video/person/313878/',
        'info_dict': {
            'id': '313878',
        },
        'playlist_mincount': 37,
    }]

    _PAGE_TEMPLATE = 'http://rutube.ru/api/video/person/%s/?page=%s&format=json'


class RutubePlaylistIE(InfoExtractor):
    IE_NAME = 'rutube:playlist'
    IE_DESC = 'Rutube playlists'
    _TESTS = [{
        'url': 'https://rutube.ru/video/10b3a03fc01d5bbcc632a2f3514e8aab/?pl_id=4252&pl_type=source',
        'info_dict': {
            'id': '4252',
        },
        'playlist_count': 25,
    }]

    _VALID_URL = r'https?://rutube\.ru/(?:video|(?:play/)?embed)/[\da-z]{32}/\?(?:.+)?pl_id=(?P<id>\d+)'
    _PAGE_TEMPLATE = 'http://rutube.ru/api/playlist/source/%s/?page=%s'

    @staticmethod
    def suitable(url):
        params = compat_parse_qs(compat_urllib_parse_urlparse(url).query)
        return params.get('pl_id') and int_or_none(params['pl_id'][0]) \
            and params.get('pl_type')

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        return self._extract_playlist(playlist_id)

    def _extract_playlist(self, playlist_id):
        entries = []
        for pagenum in itertools.count(1):
            page_url = self._PAGE_TEMPLATE % (playlist_id, pagenum)

            # download_json will sent an accept: application/xml header
            page = self._download_json(page_url, playlist_id,
                                       "Downloading metadata for page %s" % pagenum,
                                       headers={'Accept': 'application/json'})

            if not page['results']:
                break

            results = page['results']
            for result in results:
                entry = self.url_result(result.get('video_url'), 'Rutube')
                category = try_get(result, lambda x: x['category']['name'])
                entry.update({
                    'id': result.get('id'),
                    'uploader': try_get(result, lambda x: x['author']['name']),
                    'uploader_id': try_get(result, lambda x: x['author']['id']),
                    'upload_date': unified_strdate(result.get('created_ts')),
                    'title': result.get('title'),
                    'description': result.get('description'),
                    'thumbnail': result.get('thumbnail_url'),
                    'duration': int_or_none(result.get('duration')),
                    'category': [category] if category else None,
                    'age_limit': 18 if result.get('is_adult') else 0,
                    'view_count': int_or_none(result.get('hits')),
                    'is_live': result.get('is_livestream'),
                    'webpage_url': result.get('video_url'),
                })
                entries.append(entry)

            if page['has_next'] is False:
                break

        return self.playlist_result(entries, playlist_id, page['name'])
