# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from str2bool import str2bool
import os
import re
import platform
import bencodepy
import cli_ui

from src.trackers.COMMON import COMMON
from src.console import console


class HUNO():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'HUNO'
        self.source_flag = 'HUNO'
        self.search_url = 'https://hawke.uno/api/torrents/filter'
        self.upload_url = 'https://hawke.uno/api/torrents/upload'
        self.signature = "\n[center][url=https://github.com/edge20200/Only-Uploader]Powered by Only-Uploader[/url][/center]"
        self.banned_groups = ["4K4U, Bearfish, BiTOR, BONE, D3FiL3R, d3g, DTR, ELiTE, EVO, eztv, EzzRips, FGT, HashMiner, HETeam, HEVCBay, HiQVE, HR-DR, iFT, ION265, iVy, JATT, Joy, LAMA, m3th, MeGusta, MRN, Musafirboy, OEPlus, Pahe.in, PHOCiS, PSA, RARBG, RMTeam, ShieldBearer, SiQ, TBD, Telly, TSP, VXT, WKS, YAWNiX, YIFY, YTS"]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        
        # Map category_id (1 for Movies, 2 for TV)
        category_id = '1' if meta['category'] == 'MOVIE' else '2'
        
        # Map type_id (1=DISC, 2=REMUX, 3=WEB, 15=ENCODE)
        type_map = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '3',
            'WEBRIP': '3',
            'ENCODE': '15',
            'HDTV': '15',
        }
        type_id = type_map.get(meta['type'].upper(), None)
        
        # Tracker config
        tracker_config = self.config['TRACKERS'][self.tracker]
        
        # Anonymous (0 or 1, default 0)
        if meta['anon'] == 0 and bool(str2bool(tracker_config.get('anon', "False"))) is False:
            anonymous = 0
        else:
            anonymous = 1
        
        # Internal (0 or 1, only for internals)
        internal = 0
        if 'internal' in tracker_config:
            if tracker_config['internal'] and meta['tag'] and meta['tag'][1:] in tracker_config.get('internal_groups', []):
                internal = 1
        
        # Stream friendly (0 or 1)
        stream_friendly = int(await self.is_plex_friendly(meta))
        
        # Build torrent file path
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]{meta['clean_name']}.torrent"
        
        # Check if torrent file exists
        if not os.path.exists(torrent_path):
            console.print(f"[bold red]Torrent file not found: {torrent_path}[/bold red]")
            return
        
        console.print(f"[cyan]Using torrent file: {torrent_path}[/cyan]")
        
        # Prepare file uploads
        open_torrent = open(torrent_path, 'rb')
        files = {'torrent': open_torrent}
        
        # Add description file
        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]DESCRIPTION.txt"
        if os.path.exists(desc_path):
            files['description'] = open(desc_path, 'rb')
            console.print(f"[cyan]Added description file[/cyan]")
        else:
            console.print(f"[yellow]Warning: Description file not found: {desc_path}[/yellow]")
        
        # Add MediaInfo file (mandatory for non-DISC)
        if meta['bdinfo'] is None:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
            if os.path.exists(mi_path):
                files['mediainfo'] = open(mi_path, 'rb')
                console.print(f"[cyan]Added mediainfo file[/cyan]")
            else:
                console.print(f"[yellow]Warning: MediaInfo file not found: {mi_path}[/yellow]")
        
        # Add BDInfo file (mandatory for DISC)
        if meta['bdinfo'] is not None:
            bd_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_path):
                files['bdinfo'] = open(bd_path, 'rb')
                console.print(f"[cyan]Added bdinfo file[/cyan]")
            else:
                console.print(f"[yellow]Warning: BDInfo file not found: {bd_path}[/yellow]")
        
        # Add source MediaInfo file (mandatory for ENCODE)
        if meta['type'].upper() == 'ENCODE':
            source_mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/source_MEDIAINFO.txt"
            if os.path.exists(source_mi_path):
                files['source_mediainfo'] = open(source_mi_path, 'rb')
                console.print(f"[cyan]Added source mediainfo file[/cyan]")
            else:
                console.print(f"[yellow]Warning: Source MediaInfo file not found: {source_mi_path}[/yellow]")
        
        # Prepare data payload with mandatory fields (AUTO MODE handles parsing)
        data = {
            'category_id': category_id,
            'type_id': type_id,
            'anonymous': anonymous,
            'internal': internal,
            'stream_friendly': stream_friendly,
        }
        
        # Headers (Note: Don't set Content-Type manually for multipart/form-data, requests handles it)
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})',
            'Accept': 'application/json',
        }
        
        # Params with API token
        params = {
            'api_token': tracker_config['api_key'].strip()
        }
        
        console.print(f"[cyan]Uploading to {self.upload_url}[/cyan]")
        console.print(f"[cyan]Data: {data}[/cyan]")
        console.print(f"[cyan]Files: {list(files.keys())}[/cyan]")
        
        if meta['debug'] is False:
            try:
                response = requests.post(
                    url=self.upload_url,
                    files=files,
                    data=data,
                    headers=headers,
                    params=params
                )
                console.print(f"[cyan]Response status code: {response.status_code}[/cyan]")
                
                response_json = response.json()
                
                if response_json.get('success'):
                    # Extract torrent ID from response
                    torrent_id = response_json['data']['torrent']['id']
                    torrent_url = f"https://hawke.uno/torrents/{torrent_id}"
                    await common.add_tracker_torrent(
                        meta, self.tracker, self.source_flag,
                        tracker_config.get('announce_url'), torrent_url
                    )
                    # Show success message
                    console.print("[green]Torrent uploaded successfully![/green]")
                    # Display warnings if any
                    if response_json['data'].get('warnings'):
                        for warning in response_json['data']['warnings']:
                            console.print(f"[yellow]Warning: {warning}[/yellow]")
                    # Display moderation status if available
                    if response_json['data'].get('moderation_status'):
                        console.print(f"[cyan]Moderation status: {response_json['data']['moderation_status']}[/cyan]")
                else:
                    console.print("[bold red]Upload failed:[/bold red]")
                    console.print(f"[red]{response_json.get('message', 'Unknown error')}[/red]")
                    if 'data' in response_json:
                        if isinstance(response_json['data'], list):
                            for error in response_json['data']:
                                console.print(f"[red]  - {error}[/red]")
                        else:
                            console.print(f"[red]{response_json['data']}[/red]")
            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Request error: {e}[/bold red]")
                console.print(f"[red]Response text: {response.text if 'response' in locals() else 'N/A'}[/red]")
            except Exception as e:
                console.print(f"[bold red]Error during upload: {e}[/bold red]")
                console.print("It may have uploaded, go check")
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            console.print("[cyan]Files:")
            console.print(files)
        
        # Close all open files
        open_torrent.close()
        for key, file in list(files.items()):
            if key != 'torrent':
                file.close()

    def get_audio(self, meta):
        channels = meta.get('channels', "")
        codec = meta.get('audio', "").replace("DD+", "DDP").replace("EX", "").replace("Dual-Audio", "").replace(channels, "")
        dual = "Dual-Audio" in meta.get('audio', "")
        language = ""

        if dual:
            language = "DUAL"
        else:
            if not meta['is_disc']:
                # Read the MEDIAINFO.txt file
                media_info_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
                with open(media_info_path, 'r', encoding='utf-8') as f:
                    media_info_text = f.read()

                # Extract the first audio section
                first_audio_section = re.search(r'Audio\s+ID\s+:\s+2(.*?)\n\n', media_info_text, re.DOTALL)
                if not first_audio_section:  # Fallback in case of a different structure
                    first_audio_section = re.search(r'Audio(.*?)Text', media_info_text, re.DOTALL)

                if first_audio_section:
                    # Extract language information from the first audio track
                    language_match = re.search(r'Language\s*:\s*(.+)', first_audio_section.group(1))
                    if language_match:
                        language = language_match.group(1).strip()
                        language = re.sub(r'\(.+\)', '', language)  # Remove text in parentheses

        # Handle special cases
        if language == "zxx":
            language = "Silent"
        elif not language:
            language = cli_ui.ask_string('No audio language present, you must enter one:')
            if not language:
                language = "Unknown"

        return f'{codec} {channels} {language}'

    def get_basename(self, meta):
        path = next(iter(meta['filelist']), meta['path'])
        return os.path.basename(path)

    async def get_name(self, meta):
        # Copied from Prep.get_name() then modified to match HUNO's naming convention.
        # It was much easier to build the name from scratch than to alter the existing name.

        basename = self.get_basename(meta)
        hc = meta.get('hardcoded-subs')
        type = meta.get('type', "").upper()
        title = meta.get('title', "")
        alt_title = meta.get('aka', "")  # noqa F841
        year = meta.get('year', "")
        resolution = meta.get('resolution', "")
        audio = self.get_audio(meta)
        service = meta.get('service', "")
        season = meta.get('season', "")
        episode = meta.get('episode', "")
        repack = meta.get('repack', "")
        if repack.strip():
            repack = f"[{repack}]"
        three_d = meta.get('3D', "")
        tag = meta.get('tag', "").replace("-", "- ")
        if tag == "":
            tag = "- NOGRP"
        source = meta.get('source', "")
        uhd = meta.get('uhd', "")
        hdr = meta.get('hdr', "")
        if not hdr.strip():
            hdr = "SDR"
        distributor = meta.get('distributor', "")  # noqa F841
        video_codec = meta.get('video_codec', "")
        video_encode = meta.get('video_encode', "").replace(".", "")
        if 'x265' in basename:
            video_encode = video_encode.replace('H', 'x')
        region = meta.get('region', "")
        dvd_size = meta.get('dvd_size', "")
        edition = meta.get('edition', "")
        hybrid = "Hybrid" if "HYBRID" in basename.upper() else ""
        search_year = meta.get('search_year', "")
        if not str(search_year).strip():
            search_year = year
        scale = "DS4K" if "DS4K" in basename.upper() else "RM4K" if "RM4K" in basename.upper() else ""

        # YAY NAMING FUN
        if meta['category'] == "MOVIE":  # MOVIE SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({year}) {three_d} {edition} ({resolution} {region} {uhd} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'DVD':
                    name = f"{title} ({year}) {edition} ({resolution} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({year}) {edition} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay":  # BluRay Remux
                name = f"{title} ({year}) {three_d} {edition} ({resolution} {uhd} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} ({year}) {edition} ({resolution} DVD {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "ENCODE":  # Encode
                name = f"{title} ({year}) {edition} ({resolution} {scale} {uhd} {source} {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"
            elif type in ("WEBDL", "WEBRIP"):  # WEB
                name = f"{title} ({year}) {edition} ({resolution} {scale} {uhd} {service} WEB-DL {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"
            elif type == "HDTV":  # HDTV
                name = f"{title} ({year}) {edition} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"
        elif meta['category'] == "TV":  # TV SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({search_year}) {season}{episode} {three_d} {edition} ({resolution} {region} {uhd} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                if meta['is_disc'] == 'DVD':
                    name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay":  # BluRay Remux
                name = f"{title} ({search_year}) {season}{episode} {three_d} {edition} ({resolution} {uhd} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} DVD {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type == "ENCODE":  # Encode
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {scale} {uhd} {source} {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type in ("WEBDL", "WEBRIP"):  # WEB
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {scale} {uhd} {service} WEB-DL {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"
            elif type == "HDTV":  # HDTV
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"

        if hc:
            name = re.sub(r'((\([0-9]{4}\)))', r'\1 Ensubbed', name)
        return ' '.join(name.split()).replace(": ", " - ")

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, meta):
        type = meta.get('type').upper()
        video_encode = meta.get('video_encode')

        if type == 'REMUX':
            return '2'
        elif type in ('WEBDL', 'WEBRIP'):
            return '15' if 'x265' in video_encode else '3'
        elif type in ('ENCODE', 'HDTV'):
            return '15'
        elif type == 'DISC':
            return '1'
        else:
            return '0'

    async def get_res_id(self, resolution):
        resolution_id = {
            'Other': '10',
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    async def is_plex_friendly(self, meta):
        lossy_audio_codecs = ["AAC", "DD", "DD+", "OPUS"]

        if any(l in meta["audio"] for l in lossy_audio_codecs):  # noqa E741
            return 1

        return 0

    async def search_existing(self, meta, disctype):
        if meta['video_codec'] != "HEVC" and (meta['type'] == "ENCODE" or meta['type'] == "WEBRIP"):
            console.print('[bold red]Only x265/HEVC encodes are allowed')
            meta['skipping'] = "HUNO"
            return
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")

        params = {
            'api_token': self.config['TRACKERS']['HUNO']['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta),
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
