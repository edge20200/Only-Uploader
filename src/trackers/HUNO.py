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
        # Helper function for audio format extraction
        def get_audio_format_and_channel(audio_str):
            if not audio_str:
                return None, None
            
            # Extract format (codec)
            audio_format = audio_str.replace("DD+", "DDP").replace("EX", "").replace("Dual-Audio", "")
            
            # Extract channel
            channel_map = {
                '7.1': '7.1',
                '6.1': '6.1',
                '5.1': '5.1',
                '5.0': '5.0',
                '2.0': '2.0',
                '1.0': '1.0',
            }
            
            audio_channel = None
            for channel_str, api_channel in channel_map.items():
                if channel_str in audio_str:
                    audio_channel = api_channel
                    break
            
            # Clean up audio format by removing channel info and extra whitespace
            for channel_str in channel_map.keys():
                if channel_str in audio_format:
                    audio_format = audio_format.replace(channel_str, "").strip()
            
            # Map audio formats to API values
            audio_format_map = {
                'TrueHD Atmos': 'TrueHD Atmos',
                'TrueHD': 'TrueHD',
                'DTS-HD MA': 'DTS-HD MA',
                'DTS-HD HRA': 'DTS-HD HRA',
                'DTS:X': 'DTS:X',
                'DTS': 'DTS',
                'DDP Atmos': 'DDP Atmos',
                'DDP': 'DDP',
                'DD': 'DD',
                'AAC': 'AAC',
                'FLAC': 'FLAC',
                'LPCM': 'LPCM',
                'OPUS': 'OPUS',
            }
            
            # Find matching audio format
            matched_format = None
            for api_format in audio_format_map:
                if api_format.lower() in audio_format.lower():
                    matched_format = api_format
                    break
            
            if not matched_format and audio_format.strip():
                matched_format = audio_format.strip()
            
            return matched_format, audio_channel
        
        # Helper function for language extraction
        def get_media_language(meta):
            # Check if language is already provided in meta
            if meta.get('language'):
                return meta['language'].strip()
            
            # Try to extract language from audio field
            audio_str = meta.get('audio', '')
            if 'DUAL' in audio_str:
                return 'DUAL'
            
            # Fallback to English
            return 'English'
        
        # Helper function for release group
        def get_release_group(tag):
            if tag and tag.startswith('-'):
                tag = tag[1:]
            return tag if tag else 'NOGRP'
        
        # Helper function for streaming service
        def get_streaming_service(service):
            if not service:
                return None
            
            service_map = {
                'Netflix': 'NF',
                'Amazon Prime': 'AMZN',
                'Disney Plus': 'DSNP',
                'Apple TV Plus': 'ATVP',
                'HBO Max': 'MAX',
                'Hulu': 'HULU',
                'Paramount Plus': 'PCOK',
                'Peacock TV': 'PMTP',
                'HBO': 'HBO',
                'iTunes': 'iT',
            }
            
            # Case-insensitive lookup
            for full_name, code in service_map.items():
                if full_name.lower() in service.lower():
                    return code
            
            return None
        
        # Helper function for release tag
        def get_release_tag(repack):
            if repack == 'PROPER':
                return 'PROPER'
            elif repack == 'PROPER2':
                return 'PROPER2'
            elif repack == 'REPACK':
                return 'REPACK'
            else:
                return None
        
        # Helper function for releaser
        def get_releaser(tag, internal_groups):
            if not tag:
                return None
            
            # Remove leading hyphen if present
            if tag.startswith('-'):
                tag = tag[1:]
            
            # Check if tag is in banned groups (using banned_groups as reference)
            # banned_groups is a list with a single string element
            if isinstance(self.banned_groups, list):
                banned_list = [g.strip() for g in self.banned_groups]
            else:
                banned_list = [g.strip() for g in self.banned_groups.split(',')]
            
            if tag in banned_list:
                return tag
            
            return None
        
        # Helper function for scaling type
        def get_scaling_type(scale):
            if scale:
                scale_upper = scale.upper()
                if 'DS4K' in scale_upper:
                    return 'DS4K'
                elif 'RM4K' in scale_upper or 'REMASTER' in scale_upper:
                    return 'RM4K'
            return None
        
        # Helper function for region
        def get_region(region):
            if not region:
                return None
            
            region_map = {
                'A': 'RA',
                'B': 'RB',
                'C': 'RC',
                'Free': 'RF',
                'USA': 'USA',
                'GBR': 'GBR',
                'EUR': 'EUR',
                'JPN': 'JPN',
                'CAN': 'CAN',
            }
            
            return region_map.get(region.upper(), None)
        
        # Main upload logic
        common = COMMON(config=self.config)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        
        # Map category_id
        category_map = {
            'MOVIE': '1',
            'TV': '2',
        }
        category_id = category_map.get(meta['category'], None)
        
        # Map type_id
        type_map = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '3',
            'WEBRIP': '3',
            'ENCODE': '15',
            'HDTV': '15',
        }
        type_id = type_map.get(meta['type'].upper(), None)
        
        # Resolution
        resolution = meta.get('resolution', None)
        
        # Map source_type
        source = meta.get('source', '')
        if 'BluRay' in source:
            if 'UHD' in source or '4K' in source:
                source_type = 'UHD BluRay'
            else:
                source_type = 'BluRay'
        elif 'WEB-DL' in source or 'WEBDL' in source:
            source_type = 'WEB-DL'
        elif 'HDTV' in source:
            source_type = 'HDTV'
        elif 'SDTV' in source:
            source_type = 'SDTV'
        elif 'DVD9' in source:
            source_type = 'DVD9'
        elif 'DVD5' in source:
            source_type = 'DVD5'
        elif 'DVD' in source:
            source_type = 'DVD'
        elif 'HD-DVD' in source or 'HDDVD' in source:
            source_type = 'HD-DVD'
        else:
            source_type = None
        
        # Map video_codec (mandatory for non-DISC)
        video_codec = meta.get('video_codec', '')
        if video_codec:
            if 'x265' in video_codec.lower() or 'HEVC' in video_codec.upper():
                video_codec = 'x265'
            elif 'x264' in video_codec.lower() or 'H264' in video_codec.upper() or 'AVC' in video_codec.upper():
                video_codec = 'x264'
            elif 'AV1' in video_codec.upper():
                video_codec = 'AV1'
            elif 'VC-1' in video_codec:
                video_codec = 'VC-1'
            elif 'MPEG-2' in video_codec or 'MPEG2' in video_codec:
                video_codec = 'MPEG-2'
            else:
                video_codec = None
        else:
            video_codec = None
        
        if meta['is_disc'] is None and video_codec is None:
            video_codec = 'x264'  # Default for non-DISC if not specified
        
        # Map video_format (from HDR field)
        hdr = meta.get('hdr', '')
        if hdr:
            hdr_upper = hdr.upper()
            if 'HDR10+' in hdr_upper:
                video_format = 'HDR10+'
            elif 'HDR' in hdr_upper and 'DV' in hdr_upper:
                if '10+' in hdr_upper:
                    video_format = 'DV HDR10+'
                else:
                    video_format = 'DV HDR'
            elif 'DV' in hdr_upper or 'DOLBY' in hdr_upper:
                video_format = 'DV'
            elif 'HDR10' in hdr_upper or 'HDR 10' in hdr_upper:
                video_format = 'HDR10'
            elif 'HDR' in hdr_upper:
                video_format = 'HDR'
            elif 'HLG' in hdr_upper:
                video_format = 'HLG'
            elif 'PQ10' in hdr_upper:
                video_format = 'PQ10'
            else:
                video_format = 'SDR'
        else:
            video_format = 'SDR'
        
        # Extract audio_format and audio_channel
        audio_str = meta.get('audio', '')
        audio_format, audio_channel = get_audio_format_and_channel(audio_str)
        
        # Media language
        media_language = get_media_language(meta)
        
        # Release group
        release_group = get_release_group(meta.get('tag'))
        
        # Streaming service (mandatory for WEB)
        streaming_service = get_streaming_service(meta.get('service'))
        
        # Release tag
        release_tag = get_release_tag(meta.get('repack', ''))
        
        # Releaser (optional)
        tracker_config = self.config['TRACKERS'][self.tracker]
        releaser = get_releaser(meta.get('tag'), tracker_config.get('internal_groups', []))
        
        # Anonymous
        if meta['anon'] == 0 and bool(str2bool(tracker_config.get('anon', "False"))) is False:
            anonymous = 0
        else:
            anonymous = 1
        
        # Internal
        internal = 0
        if 'internal' in tracker_config:
            if tracker_config['internal'] and meta['tag'] and meta['tag'][1:] in tracker_config.get('internal_groups', []):
                internal = 1
        
        # Stream friendly
        stream_friendly = await self.is_plex_friendly(meta)
        
        # Prepare file uploads
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]{meta['clean_name']}.torrent", 'rb')
        files = {'torrent': open_torrent}
        
        # Add description file
        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]DESCRIPTION.txt"
        if os.path.exists(desc_path):
            files['description'] = open(desc_path, 'rb')
        
        # Add MediaInfo file (mandatory for non-DISC)
        if meta['bdinfo'] is None:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
            if os.path.exists(mi_path):
                files['mediainfo'] = open(mi_path, 'rb')
        
        # Add BDInfo file (mandatory for DISC)
        if meta['bdinfo'] is not None:
            bd_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_path):
                files['bdinfo'] = open(bd_path, 'rb')
        
        # Add source MediaInfo file (mandatory for ENCODE)
        if meta['type'].upper() == 'ENCODE':
            source_mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/source_MEDIAINFO.txt"
            if os.path.exists(source_mi_path):
                files['source_mediainfo'] = open(source_mi_path, 'rb')
        
        # Get season number - handle various formats
        season_value = meta.get('season')
        if season_value is None or season_value == '':
            season_number = '0'
        elif isinstance(season_value, int):
            season_number = str(season_value)
        elif isinstance(season_value, str):
            # Handle season formats like 'S01', 'E01', '01', 'E01', etc.
            # Extract digits from the season string
            season_digits = re.sub(r'[^0-9]', '', str(season_value))
            if season_digits:
                season_number = season_digits
            else:
                season_number = '0'
        else:
            season_number = '0'
        
        # Prepare data payload
        data = {
            'mode': 'manual',
            'name': await self.get_name(meta),
            'category_id': category_id,
            'type_id': type_id,
            'tmdb': meta['tmdb'],
            'anonymous': anonymous,
            'internal': internal,
            'stream_friendly': stream_friendly,
            'season_number': season_number,
        }
        
        # Add non-DISC mandatory fields
        if meta['is_disc'] is None:
            if source_type:
                data['source_type_id'] = source_type
            if video_codec:
                data['video_codec_id'] = video_codec
            if video_format:
                data['video_format_id'] = video_format
            if audio_format:
                data['audio_format_id'] = audio_format
            if audio_channel:
                data['audio_channel_id'] = audio_channel
            if resolution:
                data['resolution_id'] = resolution
            if media_language:
                data['media_language_id'] = media_language
        
        # Add optional fields
        if release_group:
            data['release_group'] = release_group
        
        if streaming_service:
            data['streaming_service'] = streaming_service
        
        if release_tag:
            data['release_tag'] = release_tag
        
        if releaser:
            data['releaser'] = releaser
        
        # TV-specific fields
        if meta['category'] == 'TV':
            if meta.get('tv_pack') == 1:
                data['season_pack'] = '1'
            elif meta.get('episode') and meta['episode'] != 0:
                data['episode_number'] = str(meta['episode'])
        
        # Optional fields from meta
        if meta.get('imdb_id'):
            data['imdb'] = meta['imdb_id'].replace('tt', '')
        
        if meta.get('tvdb_id'):
            data['tvdb'] = str(meta['tvdb_id'])
        elif meta['category'] == 'MOVIE':
            data['tvdb'] = '0'
        
        if meta.get('distributor'):
            data['distributor'] = meta['distributor']
        
        if meta.get('edition'):
            data['edition'] = meta['edition']
        
        region = get_region(meta.get('region'))
        if region:
            data['region'] = region
        
        scaling_type = get_scaling_type(meta.get('scale'))
        if scaling_type:
            data['scaling_type'] = scaling_type
        
        # Headers
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})',
            'Accept': 'application/json',
        }
        
        # Params with API token
        params = {
            'api_token': tracker_config['api_key'].strip()
        }
        
        if meta['debug'] is False:
            response = requests.post(
                url=self.upload_url,
                files=files,
                data=data,
                headers=headers,
                params=params
            )
            try:
                response_json = response.json()
                
                if response_json.get('success'):
                    # Extract torrent ID from response
                    torrent_id = response_json['data']['torrent']['id']
                    torrent_url = f"https://hawke.uno/torrents/{torrent_id}"
                    await common.add_tracker_torrent(
                        meta, self.tracker, self.source_flag,
                        tracker_config.get('announce_url'), torrent_url
                    )
                    # Show simplified success message instead of full JSON
                    console.print("[green]Torrent uploaded successfully![/green]")
                else:
                    console.print("[bold red]Upload failed:")
                    console.print(response_json.get('message', 'Unknown error'))
                    if 'data' in response_json:
                        console.print(response_json['data'])
            except Exception as e:
                console.print(f"[bold red]Error during upload: {e}")
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
