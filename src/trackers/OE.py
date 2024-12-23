# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from str2bool import str2bool
import platform
import re
import os
import cli_ui
from src.bbcode import BBCODE
from src.trackers.COMMON import COMMON
from src.console import console
import bencodepy


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
        self.torrent_url = 'https://onlyencodes.cc/api/torrents/'
        self.signature = "\n[center][url=https://github.com/edge20200/Only-Uploader]Powered by Only-Uploader[/url][/center]"
        self.banned_groups = [
            '0neshot', '3LT0N', '4K4U', '4yEo', '$andra', '[Oj]', 'AFG', 'AkihitoSubs', 'AniHLS', 'Anime Time',
            'AnimeRG', 'AniURL', 'AOC', 'AR', 'AROMA', 'ASW', 'aXXo', 'BakedFish', 'BiTOR', 'BRrip', 'bonkai',
            'Cleo', 'CM8', 'C4K', 'CrEwSaDe', 'core', 'd3g', 'DDR', 'DE3PM', 'DeadFish', 'DeeJayAhmed', 'DNL', 'ELiTE',
            'EMBER', 'eSc', 'EVO', 'EZTV', 'FaNGDiNG0', 'FGT', 'fenix', 'FUM', 'FRDS', 'FROZEN', 'GalaxyTV',
            'GalaxyRG', 'GalaxyRG265', 'GERMini', 'Grym', 'GrymLegacy', 'HAiKU', 'HD2DVD', 'HDTime', 'Hi10',
            'HiQVE', 'ION10', 'iPlanet', 'JacobSwaggedUp', 'JIVE', 'Judas', 'KiNGDOM', 'LAMA', 'Leffe', 'LiGaS',
            'LOAD', 'LycanHD', 'MeGusta', 'MezRips', 'mHD', 'Mr.Deadpool', 'mSD', 'NemDiggers', 'neoHEVC', 'NeXus',
            'nHD', 'nikt0', 'nSD', 'NhaNc3', 'NOIVTC', 'pahe.in', 'PlaySD', 'playXD', 'PRODJi', 'ProRes',
            'project-gxs', 'PSA', 'QaS', 'Ranger', 'RAPiDCOWS', 'RARBG', 'Raze', 'RCDiVX', 'RDN', 'Reaktor',
            'REsuRRecTioN', 'RMTeam', 'ROBOTS', 'rubix', 'SANTi', 'SHUTTERSHIT', 'SpaceFish', 'SPASM', 'SSA',
            'TBS', 'Telly', 'Tenrai-Sensei', 'TERMiNAL', 'TGx', 'TM', 'topaz', 'TSP', 'TSPxL', 'URANiME', 'UTR',
            'VipapkSudios', 'ViSION', 'WAF', 'Wardevil', 'x0r', 'xRed', 'XS', 'YakuboEncodes', 'YIFY', 'YTS',
            'YuiSubs', 'ZKBL', 'ZmN', 'ZMNT'
        ]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta, self.tracker, self.signature)
        cat_id = await self.get_cat_id(meta['category'])
        if meta.get('type') == "DVDRIP":
            meta['type'] = "ENCODE"
        type_id = await self.get_type_id(meta['type'], meta.get('tv_pack', 0), meta.get('video_codec'), meta.get('category', ""))
        resolution_id = await self.get_res_id(meta['resolution'])
        oe_name = await self.edit_name(meta)
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
                open_torrent.close()
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        open_torrent.close()

    async def edit_name(self, meta):
        oe_name = meta.get('name')
        media_info_tracks = meta.get('media_info_tracks', [])  # noqa #F841
        resolution = meta.get('resolution')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if name_type == "DVDRIP":
            if meta.get('category') == "MOVIE":
                oe_name = oe_name.replace(f"{meta['source']}{meta['video_encode']}", f"{resolution}", 1)
                oe_name = oe_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)
            else:
                oe_name = oe_name.replace(f"{meta['source']}", f"{resolution}", 1)
                oe_name = oe_name.replace(f"{meta['video_codec']}", f"{meta['audio']} {meta['video_codec']}", 1)

        if not meta['is_disc']:
            def has_english_audio(media_info_text=None):
                if media_info_text:
                    audio_section = re.findall(r'Audio[\s\S]+?Language\s+:\s+(\w+)', media_info_text)
                    for i, language in enumerate(audio_section):
                        language = language.lower().strip()
                        if language.lower().startswith('en'):  # Check if it's English
                            return True
                return False

            def get_audio_lang(media_info_text=None):
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
                        oe_name = oe_name.replace(meta['resolution'], f"{audio_lang} {meta['resolution']}", 1)
            except (FileNotFoundError, KeyError) as e:
                print(f"Error processing MEDIAINFO.txt: {e}")

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                oe_name = re.sub(f"-{invalid_tag}", "", oe_name, flags=re.IGNORECASE)
            oe_name = f"{oe_name}-NOGRP"

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

    async def edit_desc(self, meta, tracker, signature, comparison=False, desc_header=""):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf8').read()

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.txt", 'w', encoding='utf8') as descfile:
            if desc_header != "":
                descfile.write(desc_header)

            if not meta['is_disc']:
                def process_languages(tracks):
                    audio_languages = []
                    subtitle_languages = []

                    for track in tracks:
                        if track.get('@type') == 'Audio':
                            language = track.get('Language')
                            if not language or language is None:
                                audio_lang = cli_ui.ask_string('No audio language present, you must enter one:')
                                if audio_lang:
                                    audio_languages.append(audio_lang)
                                else:
                                    audio_languages.append("")
                        if track.get('@type') == 'Text':
                            language = track.get('Language')
                            if not language or language is None:
                                subtitle_lang = cli_ui.ask_string('No subtitle language present, you must enter one:')
                                if subtitle_lang:
                                    subtitle_languages.append(subtitle_lang)
                                else:
                                    subtitle_languages.append("")

                    return audio_languages, subtitle_languages

                media_data = meta.get('mediainfo', {})
                if media_data:
                    tracks = media_data.get('media', {}).get('track', [])
                    if tracks:
                        audio_languages, subtitle_languages = process_languages(tracks)
                        if audio_languages:
                            descfile.write(f"Audio Language: {', '.join(audio_languages)}\n")

                        subtitle_tracks = [track for track in tracks if track.get('@type') == 'Text']
                        if subtitle_tracks and subtitle_languages:
                            descfile.write(f"Subtitle Language: {', '.join(subtitle_languages)}\n")
                else:
                    console.print("[red]No media information available in meta.[/red]")

            # Existing disc metadata handling
            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    descfile.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]\n\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n")
                        elif each['type'] == "DVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]\n\n")
                        elif each['type'] == "HDDVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['largest_evo'])}][code][{each['evo_mi']}[/code][/spoiler]\n\n")

            desc = base
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)

            desc = desc.replace('[img]', '[img=300]')
            descfile.write(desc)
            images = meta['image_list']
            if len(images) > 0:
                descfile.write("[center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    raw_url = images[each]['raw_url']
                    descfile.write(f"[url={web_url}][img=350]{raw_url}[/img][/url]")
                descfile.write("[/center]")

            if signature is not None:
                descfile.write(signature)
        return

    async def search_existing(self, meta, disctype):
        if 'concert' in meta['keywords']:
            console.print('[bold red]Concerts not allowed.')
            meta['skipping'] = "OE"
            return
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