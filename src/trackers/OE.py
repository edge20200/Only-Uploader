# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from str2bool import str2bool
import platform

from src.trackers.COMMON import COMMON
from src.console import console


class OE():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'OE'
        self.source_flag = 'OE'
        self.search_url = 'https://onlyencodes.cc/api/torrents/filter'
        self.upload_url = 'https://onlyencodes.cc/api/torrents/upload'
        self.signature = f"\n[center][url=https://onlyencodes.cc/wikis/17]Powered by Only-Uploader[/url][/center]"
        self.banned_groups = ['0neshot', '3LT0N', '4K4U', '4yEo', '$andra', '[Oj]', 'AFG', 'AkihitoSubs', 'AniHLS', 'Anime Time', 'AnimeRG', 'AniURL', 'AR', 'AROMA', 'ASW', 'aXXo', 'BakedFish', 'BiTOR', 'BHDStudio', 'BRrip', 'bonkai', 'Cleo', 'CM8', 'C4K', 'CrEwSaDe', 'core', 'd3g', 'DDR', 'DeadFish', 'DeeJayAhmed', 'DNL', 'ELiTE', 'EMBER', 'eSc', 'EVO', 'EZTV', 'FaNGDiNG0', 'FGT', 'fenix', 'FUM', 'FRDS', 'FROZEN', 'GalaxyTV', 'GalaxyRG', 'GERMini', 'Grym', 'GrymLegacy', 'HAiKU', 'HD2DVD', 'HDTime', 'Hi10', 'ION10', 'iPlanet', 'JacobSwaggedUp', 'JIVE', 'Judas', 'KiNGDOM', 'LAMA', 'Leffe', 'LiGaS', 'LOAD', 'LycanHD', 'MeGusta,' 'MezRips,' 'mHD,' 'Mr.Deadpool', 'mSD', 'NemDiggers', 'neoHEVC', 'NeXus', 'NhaNc3', 'nHD', 'nikt0', 'nSD', 'NhaNc3', 'NOIVTC', 'pahe.in', 'PlaySD', 'playXD', 'PRODJi', 'ProRes', 'project-gxs', 'PSA', 'QaS', 'Ranger', 'RAPiDCOWS', 'RARBG', 'Raze', 'RCDiVX', 'RDN', 'Reaktor', 'REsuRRecTioN', 'RMTeam', 'ROBOTS', 'rubix', 'SANTi', 'SHUTTERSHIT', 'SpaceFish', 'SPASM', 'SSA', 'TBS', 'Telly,' 'Tenrai-Sensei,' 'TERMiNAL,' 'TM', 'topaz', 'TSP', 'TSPxL', 'Trix', 'URANiME', 'UTR', 'VipapkSudios', 'ViSION', 'WAF', 'Wardevil', 'x0r', 'xRed', 'XS', 'YakuboEncodes', 'YIFY', 'YTS', 'YuiSubs', 'ZKBL', 'ZmN', 'ZMNT']
        pass

    async def upload(self, meta):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'], meta.get('tv_pack', 0), meta.get('video_codec'), meta.get('category', ""))
        resolution_id = await self.get_res_id(meta['resolution'])
        oe_name = await self.edit_name(meta)
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
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name': oe_name,
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

                console.print(response.json())
            except Exception:
                console.print("It may have uploaded, go check")
                open_torrent.close()
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        open_torrent.close()

    async def edit_name(self, meta):
        oe_name = meta.get('name')
        return oe_name

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, type, tv_pack, video_codec, category):
        type_id = {
            'DISC': '19',
            'REMUX': '20',
            'WEBDL': '21',
        }.get(type, '0')
        if type == "WEBRIP":
            if video_codec == "HEVC":
                # x265 Encode
                type_id = '10'
            if video_codec == 'AV1':
                # AV1 Encode
                type_id = '14'
            if video_codec == 'AVC':
                # x264 Encode
                type_id = '15'
        if type == "ENCODE":
            if video_codec == "HEVC":
                # x265 Encode
                type_id = '10'
            if video_codec == 'AV1':
                # AV1 Encode
                type_id = '14'
            if video_codec == 'AVC':
                # x264 Encode
                type_id = '15'
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

    async def search_existing(self, meta):
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