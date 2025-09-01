import asyncio
import requests
import platform
import re
import os
import glob
import bencodepy
from str2bool import str2bool
from src.trackers.COMMON import COMMON
from src.console import console


class SP():
    def __init__(self, config):
        self.config = config
        self.tracker = 'SP'
        self.source_flag = 'seedpool.org'
        self.upload_url = 'https://seedpool.org/api/torrents/upload'
        self.search_url = 'https://seedpool.org/api/torrents/filter'
        self.torrent_url = 'https://seedpool.org/torrents/'
        self.signature = "\n[center][url=https://github.com/edge20200/Only-Uploader]Powered by Only-Uploader[/url][/center]"
        self.banned_groups = []

    async def get_cat_id(self, meta):
        category_name = meta.get('category', '').upper()
        release_title = meta.get('name', '')
        mal_id = meta.get('mal_id', 0)
        tv_pack = meta.get('tv_pack', 0)

        if mal_id != 0:
            return '6'
        if tv_pack != 0:
            return '13'
        if self.contains_sports_patterns(release_title):
            return '8'

        return {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')

    def contains_sports_patterns(self, release_title):
        patterns = [
            r'EFL.*', r'.*mlb.*', r'.*formula1.*', r'.*nascar.*', r'.*nfl.*', r'.*wrc.*', r'.*wwe.*',
            r'.*fifa.*', r'.*boxing.*', r'.*rally.*', r'.*ufc.*', r'.*ppv.*', r'.*uefa.*', r'.*nhl.*',
            r'.*nba.*', r'.*motogp.*', r'.*moto2.*', r'.*moto3.*', r'.*gamenight.*', r'.*darksport.*',
            r'.*overtake.*'
        ]
        for pattern in patterns:
            if re.search(pattern, release_title, re.IGNORECASE):
                return True
        return False

    async def get_type_id(self, type):
        return {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DVDRIP': '3'
        }.get(type, '0')

    async def get_res_id(self, resolution):
        return {
            '8640p': '10',
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0
        return 1 if meta.get(flag_name, False) else 0

    async def edit_name(self, meta):
        KNOWN_EXTENSIONS = {".mkv", ".mp4", ".avi", ".ts"}
        if meta['scene'] is True:
            name = meta.get('scene_name') or meta['uuid'].replace(" ", ".")
        elif meta.get('is_disc') is True:
            name = meta['name'].replace(" ", ".")
        elif meta.get('mal_id', 0) != 0:
            name = meta['name'].replace(" ", ".")
        else:
            name = meta['uuid'].replace(" ", ".")
        base, ext = os.path.splitext(name)
        if ext.lower() in KNOWN_EXTENSIONS:
            name = base.replace(" ", ".")
        console.print(f"[cyan]Name: {name}")
        return name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)

        cat_id = await self.get_cat_id(meta)
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        modq = await self.get_flag(meta, 'modq')
        name = await self.edit_name(meta)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))

        anon_config = self.config['TRACKERS'][self.tracker].get('anon', False)
        anon = 1 if meta['anon'] == 1 or str2bool(str(anon_config)) else 0

        if meta['bdinfo']:
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
            mi_dump = None
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None

        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb')

        files = {'torrent': open_torrent}
        nfo_path = glob.glob(os.path.join(meta['base_dir'], "tmp", meta['uuid'], "*.nfo"))
        if nfo_path:
            files['nfo'] = ("nfo_file.nfo", open(nfo_path[0], 'rb'), "text/plain")

        data = {
            'name': name,
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb_id'].replace('tt', ''),
            'tvdb': meta['tvdb_id'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            'personal_release': int(meta.get('personalrelease', False)),
            'internal': 0,
            'featured': 0,
            'free': 0,
            'doubleup': 0,
            'sticky': 0,
            'mod_queue_opt_in': modq,
        }

        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1

        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')

        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                console.print(response.json())
            except Exception:
                console.print("It may have uploaded, go check")
        else:
            console.print("[cyan]Request Data:")
            console.print(data)

        open_torrent.close()

    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")

        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }

        if meta['category'] == 'TV':
            params['name'] += f" {meta.get('season', '')}{meta.get('episode', '')}"

        if meta.get('edition', "") != "":
            params['name'] += f" {meta['edition']}"

        try:
            response = requests.get(url=self.search_url, params=params)
            response = response.json()
            for each in response['data']:
                result = each['attributes']['name']
                dupes.append(result)
        except Exception:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes
