# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from str2bool import str2bool
import platform
import re
import bencodepy
import os
import glob

from src.trackers.COMMON import COMMON
from src.console import console


class AITHER():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'AITHER'
        self.source_flag = 'Aither'
        self.search_url = 'https://aither.cc/api/torrents/filter'
        self.upload_url = 'https://aither.cc/api/torrents/upload'
        self.torrent_url = 'https://aither.cc/api/torrents/'
        self.signature = "\n[center][url=https://github.com/edge20200/Only-Uploader]Powered by Only-Uploader[/url][/center]"
        self.banned_groups = [
            '4K4U', 'afm72', 'AROMA', 'Bandi', 'BiTOR', 'Bluespots', 'Chivaman', 'd3g', 'edge2020', 'EMBER', 'EVO', 'FGT', 'FreetheFish', 'Garshasp', 'Ghost', 'Grym', 'Hi10', 'HiQVE', 'ImE', 'ION10',
            'iVy', 'Judas', 'LAMA', 'Langbard', 'LION', 'MeGusta', 'MONOLITH', 'Natty', 'nikt0', 'noxxus', 'OEPlus', 'OFT', 'OsC', 'Panda', 'PYC', 'QxR', 'r00t', 'Ralphy', 'RARBG', 'RCVR', 'RetroPeeps',
            'RZeroX', 'SAMPA', 'Sicario', 'Silence', 'SkipTT', 'SM737', 'SPDVD', 'STUTTERSHIT', 'SWTYBLZ', 't3nzin', 'TAoE', 'Telly', 'TGx', 'Tigole', 'TSP', 'TSPxL', 'VXT', 'Vyndros', 'Weasley[HONE]',
            'Will1869', 'x0r', 'YIFY']
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature, comparison=True)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        modq = await self.get_flag(meta, 'modq')
        name = await self.edit_name(meta)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
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
        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)
        nfo_file = None
        if nfo_files:
            nfo_file = open(nfo_files[0], 'rb')
        if nfo_file:
            files['nfo'] = ("nfo_file.nfo", nfo_file, "text/plain")
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
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        # Internal
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
        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                console.print(response.json())
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        open_torrent.close()

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def edit_name(self, meta):
        aither_name = meta['name']
        media_info_tracks = meta.get('media_info_tracks', [])  # noqa #F841
        resolution = meta.get('resolution')
        video_codec = meta.get('video_codec')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")

        if name_type == "DVDRIP":
            if meta.get('category') == "MOVIE":
                aither_name = aither_name.replace(f"{meta['source']}{meta['video_encode']}", f"{resolution}", 1)
                aither_name = aither_name.replace((meta['audio']), f"{meta['audio']} {video_encode}", 1)
            else:
                aither_name = aither_name.replace(f"{meta['source']}", f"{resolution}", 1)
                aither_name = aither_name.replace(f"{meta['video_codec']}", f"{meta['audio']} {meta['video_codec']}", 1)

        if not meta['is_disc']:

            def has_english_audio(tracks=None, media_info_text=None):
                if media_info_text:
                    audio_section = re.findall(r'Audio[\s\S]+?Language\s+:\s+(\w+)', media_info_text)
                    for i, language in enumerate(audio_section):
                        language = language.lower().strip()
                        if language.lower().startswith('en'):  # Check if it's English
                            return True
                return False

            def get_audio_lang(tracks=None, is_bdmv=False, media_info_text=None):
                if media_info_text:
                    match = re.search(r'Audio[\s\S]+?Language\s+:\s+(\w+)', media_info_text)
                    if match:
                        return match.group(1).upper()
                return ""

            try:
                media_info_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
                with open(media_info_path, 'r', encoding='utf-8') as f:
                    media_info_text = f.read()

                if not has_english_audio(media_info_text=media_info_text):
                    audio_lang = get_audio_lang(media_info_text=media_info_text)
                    if audio_lang:
                        if (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
                            aither_name = aither_name.replace(str(meta['year']), f"{meta['year']} {audio_lang}", 1)
                        else:
                            aither_name = aither_name.replace(meta['resolution'], f"{audio_lang} {meta['resolution']}", 1)
            except (FileNotFoundError, KeyError) as e:
                print(f"Error processing MEDIAINFO.txt: {e}")

        if meta['is_disc'] == "DVD" or (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            aither_name = aither_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
            aither_name = aither_name.replace((meta['audio']), f"{video_codec} {meta['audio']}", 1)

        if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 and meta.get('episode_title_storage', '').strip() != '' and meta['episode'].strip() != '':
            aither_name = aither_name.replace(meta['episode'], f"{meta['episode']} {meta['episode_title_storage']}", 1)

        return aither_name

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, type):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DVDRIP': '3'
        }.get(type, '0')
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
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}{meta.get('episode', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + f" {meta['edition']}"

        try:
            response = requests.get(url=self.search_url, params=params)
            response = response.json()
            for each in response['data']:
                result = [each][0]['attributes']['name']
                # difference = SequenceMatcher(None, meta['clean_name'], result).ratio()
                # if difference >= 0.05:
                dupes.append(result)
        except Exception:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes

    async def search_torrent_page(self, meta, disctype):
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        Name = meta['name']
        quoted_name = f'"{Name}"'

        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'name': quoted_name
        }

        try:
            response = requests.get(url=self.search_url, params=params)
            response.raise_for_status()
            response_data = response.json()

            if response_data['data'] and isinstance(response_data['data'], list):
                details_link = response_data['data'][0]['attributes'].get('details_link')

                if details_link:
                    with open(torrent_file_path, 'rb') as open_torrent:
                        torrent_data = open_torrent.read()

                    torrent = bencodepy.decode(torrent_data)
                    torrent[b'comment'] = details_link.encode('utf-8')
                    updated_torrent_data = bencodepy.encode(torrent)

                    with open(torrent_file_path, 'wb') as updated_torrent_file:
                        updated_torrent_file.write(updated_torrent_data)

                    return details_link
                else:
                    return None
            else:
                return None

        except requests.exceptions.RequestException as e:
            print(f"An error occurred during the request: {e}")
            return None