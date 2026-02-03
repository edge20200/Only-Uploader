# -*- coding: utf-8 -*-
import asyncio
import requests
from str2bool import str2bool
import platform

from src.trackers.COMMON import COMMON
from src.console import console


class STC():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'STC'
        self.source_flag = 'STC'
        self.upload_url = 'https://skipthecommercials.xyz/api/torrents/upload'
        self.search_url = 'https://skipthecommercials.xyz/api/torrents/filter'
        self.signature = "\n[center][url=https://github.com/edge20200/Only-Uploader]Powered by Only-Uploader[/url][/center]"
        self.banned_groups = [""]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'], meta.get('tv_pack', 0), meta.get('sd', 0), meta.get('category', ""))
        resolution_id = await self.get_res_id(meta['resolution'])
        stc_name = await self.edit_name(meta)
        if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) is False:
            anon = 0
        else:
            anon = 1
        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name': stc_name,
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
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1

        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {
            'User-Agent': f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                response_json = response.json()
                console.print(response_json)
                # Download the .torrent file from the tracker after successful upload
                if response.status_code in (200, 201) and 'data' in response_json:
                    download_url = response_json['data']
                    if download_url.startswith('http') and 'torrent/download' in download_url:
                        await self.download_torrent_file(download_url, meta, self.tracker, self.config['TRACKERS'][self.tracker]['api_key'].strip())
            except Exception:
                console.print("It may have uploaded, go check")
                open_torrent.close()
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        open_torrent.close()

    async def download_torrent_file(self, download_url, meta, tracker_name, api_key):
        """Download .torrent file from tracker after successful upload"""
        try:
            headers = {
                'User-Agent': f'Upload Assistant/2.1 ({platform.system()} {platform.release()})',
                'Authorization': f'Bearer {api_key}'
            }
            
            response = requests.get(download_url, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            # Save the downloaded .torrent file with STC-specific key
            downloaded_torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker_name}]{meta['clean_name']}_DOWNLOADED.torrent"
            with open(downloaded_torrent_path, 'wb') as f:
                f.write(response.content)
            
            console.print(f"[green]Downloaded .torrent file from tracker: {downloaded_torrent_path}")
            
            # Store in tracker-specific metadata to avoid conflicts with other trackers
            if 'downloaded_torrents' not in meta:
                meta['downloaded_torrents'] = {}
            meta['downloaded_torrents'][tracker_name] = downloaded_torrent_path
            
        except Exception as e:
            console.print(f"[red]Failed to download .torrent file from tracker: {e}")

    async def edit_name(self, meta):
        stc_name = meta.get('name')
        return stc_name

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, type, tv_pack, sd, category):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        if tv_pack == 1:
            if sd == 1:
                # Season SD
                type_id = '14'
                if type == "ENCODE":
                    type_id = '18'
            if sd == 0:
                # Season HD
                type_id = '13'
                if type == "ENCODE":
                    type_id = '18'
        if type == "DISC" and category == "TV":
            if sd == 1:
                # SD-RETAIL
                type_id = '17'
            if sd == 0:
                # HD-RETAIL
                type_id = '18'
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
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
        return resolution_id

    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type'], meta.get('tv_pack', 0), meta.get('sd', 0), meta.get('category', "")),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}{meta.get('episode', '')}"
        if meta.get('edition', "") != "":
            params['name'] + meta['edition']
        try:
            response = requests.get(url=self.search_url, params=params)
            response = response.json()
            for each in response['data']:
                result = [each][0]['attributes']['name']
                dupes.append(result)
        except Exception:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes
