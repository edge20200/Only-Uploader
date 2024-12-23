# -*- coding: utf-8 -*-
from torf import Torrent
import xmlrpc.client
import bencode
import os
import qbittorrentapi
from deluge_client import DelugeRPCClient
import base64
from pyrobase.parts import Bunch
import errno
import asyncio
import ssl
import shutil
import time
from src.console import console
import re


class Clients():
    """
    Add to torrent client
    """
    def __init__(self, config):
        self.config = config
        pass

    async def add_to_client(self, meta, tracker):
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]{meta['clean_name']}.torrent"
        if meta.get('no_seed', False) is True:
            console.print("[bold red]--no-seed was passed, so the torrent will not be added to the client")
            console.print("[bold yellow]Add torrent manually to the client")
            return
        if os.path.exists(torrent_path):
            torrent = Torrent.read(torrent_path)
        else:
            return
        if meta.get('client', None) is None:
            default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        else:
            default_torrent_client = meta['client']
        if meta.get('client', None) == 'none':
            return
        if default_torrent_client == "none":
            return
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_client = client['torrent_client']

        local_path, remote_path = await self.remote_path_map(meta)

        console.print(f"[bold green]Adding to {torrent_client}")
        if torrent_client.lower() == "rtorrent":
            self.rtorrent(meta['path'], torrent_path, torrent, meta, local_path, remote_path, client)
        elif torrent_client == "qbit":
            await self.qbittorrent(meta['path'], torrent, local_path, remote_path, client, meta['is_disc'], meta['filelist'], meta)
        elif torrent_client.lower() == "deluge":
            if meta['type'] == "DISC":
                path = os.path.dirname(meta['path'])  # noqa F841
            self.deluge(meta['path'], torrent_path, torrent, local_path, remote_path, client, meta)
        elif torrent_client.lower() == "watch":
            shutil.copy(torrent_path, client['watch_folder'])
        return

    async def find_existing_torrent(self, meta):
        if meta.get('client', None) is None:
            default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        else:
            default_torrent_client = meta['client']
        if meta.get('client', None) == 'none' or default_torrent_client == 'none':
            return None
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_storage_dir = client.get('torrent_storage_dir')
        torrent_client = client.get('torrent_client', '').lower()

        if torrent_storage_dir is None and torrent_client != "watch":
            console.print(f'[bold red]Missing torrent_storage_dir for {default_torrent_client}')
            return None
        if not os.path.exists(str(torrent_storage_dir)) and torrent_client != "watch":
            console.print(f"[bold red]Invalid torrent_storage_dir path: [bold yellow]{torrent_storage_dir}")

        torrenthash = None
        for hash_key in ['torrenthash', 'ext_torrenthash']:
            hash_value = meta.get(hash_key)
            if hash_value:
                valid, torrent_path = await self.is_valid_torrent(
                    meta, f"{torrent_storage_dir}/{hash_value}.torrent",
                    hash_value, torrent_client, print_err=True
                )
                if valid:
                    torrenthash = hash_value
                    break

        if torrent_client == 'qbit' and not torrenthash and client.get('enable_search'):
            torrenthash = await self.search_qbit_for_torrent(meta, client)

        if torrenthash:
            torrent_path = f"{torrent_storage_dir}/{torrenthash}.torrent"
            valid2, torrent_path = await self.is_valid_torrent(
                meta, torrent_path, torrenthash, torrent_client, print_err=False
            )
            if valid2:
                return torrent_path

        console.print("[bold yellow]No Valid .torrent found")
        return None

    async def is_valid_torrent(self, meta, torrent_path, torrenthash, torrent_client, print_err=False):
        valid = False
        wrong_file = False

        # Normalize the torrent hash based on the client
        if torrent_client in ('qbit', 'deluge'):
            torrenthash = torrenthash.lower().strip()
            torrent_path = torrent_path.replace(torrenthash.upper(), torrenthash)
        elif torrent_client == 'rtorrent':
            torrenthash = torrenthash.upper().strip()
            torrent_path = torrent_path.replace(torrenthash.upper(), torrenthash)

        if meta['debug']:
            console.log(f"Torrent path after normalization: {torrent_path}")

        # Check if torrent file exists
        if os.path.exists(torrent_path):
            try:
                torrent = Torrent.read(torrent_path)
            except Exception as e:
                console.print(f'[bold red]Error reading torrent file: {e}')
                return valid, torrent_path

            # Reuse if disc and basename matches or --keep-folder was specified
            if meta.get('is_disc', None) is not None or (meta['keep_folder'] and meta['isdir']):
                torrent_name = torrent.metainfo['info']['name']
                if meta['uuid'] != torrent_name:
                    console.print("Modified file structure, skipping hash")
                    valid = False
                torrent_filepath = os.path.commonpath(torrent.files)
                if os.path.basename(meta['path']) in torrent_filepath:
                    valid = True
                if meta['debug']:
                    console.log(f"Torrent is valid based on disc/basename or keep-folder: {valid}")

            # If one file, check for folder
            elif len(torrent.files) == len(meta['filelist']) == 1:
                if os.path.basename(torrent.files[0]) == os.path.basename(meta['filelist'][0]):
                    if str(torrent.files[0]) == os.path.basename(torrent.files[0]):
                        valid = True
                    else:
                        wrong_file = True
                if meta['debug']:
                    console.log(f"Single file match status: valid={valid}, wrong_file={wrong_file}")

            # Check if number of files matches number of videos
            elif len(torrent.files) == len(meta['filelist']):
                torrent_filepath = os.path.commonpath(torrent.files)
                actual_filepath = os.path.commonpath(meta['filelist'])
                local_path, remote_path = await self.remote_path_map(meta)

                if local_path.lower() in meta['path'].lower() and local_path.lower() != remote_path.lower():
                    actual_filepath = actual_filepath.replace(local_path, remote_path).replace(os.sep, '/')

                if meta['debug']:
                    console.log(f"Torrent_filepath: {torrent_filepath}")
                    console.log(f"Actual_filepath: {actual_filepath}")

                if torrent_filepath in actual_filepath:
                    valid = True
                if meta['debug']:
                    console.log(f"Multiple file match status: valid={valid}")

        else:
            console.print(f'[bold yellow]{torrent_path} was not found')

        # Additional checks if the torrent is valid so far
        if valid:
            if os.path.exists(torrent_path):
                try:
                    reuse_torrent = Torrent.read(torrent_path)
                    if meta['debug']:
                        console.log(f"Checking piece size and count: pieces={reuse_torrent.pieces}, piece_size={reuse_torrent.piece_size}")

                    # Piece size and count validations
                    if (reuse_torrent.pieces >= 7000 and reuse_torrent.piece_size < 8388608) or (reuse_torrent.pieces >= 4000 and reuse_torrent.piece_size < 4194304):
                        console.print("[bold yellow]Too many pieces exist in current hash. REHASHING")
                        valid = False
                    elif reuse_torrent.piece_size < 32768:
                        console.print("[bold yellow]Piece size too small to reuse")
                        valid = False
                    elif wrong_file:
                        console.print("[bold red] Provided .torrent has files that were not expected")
                        valid = False
                    else:
                        console.print(f"[bold green]REUSING .torrent with infohash: [bold yellow]{torrenthash}")
                except Exception as e:
                    console.print(f'[bold red]Error checking reuse torrent: {e}')
                    valid = False

            if meta['debug']:
                console.log(f"Final validity after piece checks: valid={valid}")
        else:
            console.print("[bold yellow]Unwanted Files/Folders Identified")

        return valid, torrent_path

    async def search_qbit_for_torrent(self, meta, client):
        console.print("[green]Searching qbittorrent for an existing .torrent")
        torrent_storage_dir = client.get('torrent_storage_dir', None)
        if meta['debug']:
            if torrent_storage_dir:
                console.print(f"Torrent storage directory found: {torrent_storage_dir}")
            else:
                console.print("No torrent storage directory found.")
        if torrent_storage_dir is None and client.get("torrent_client", None) != "watch":
            console.print(f"[bold red]Missing torrent_storage_dir for {self.config['DEFAULT']['default_torrent_client']}")
            return None

        try:
            qbt_client = qbittorrentapi.Client(host=client['qbit_url'], port=client['qbit_port'], username=client['qbit_user'], password=client['qbit_pass'], VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True))
            qbt_client.auth_log_in()
            if meta['debug']:
                console.print("We logged into qbittorrent")
        except qbittorrentapi.LoginFailed:
            console.print("[bold red]INCORRECT QBIT LOGIN CREDENTIALS")
            return None
        except qbittorrentapi.APIConnectionError:
            console.print("[bold red]APIConnectionError: INCORRECT HOST/PORT")
            return None

        # Remote path map if needed
        remote_path_map = False
        local_path, remote_path = await self.remote_path_map(meta)
        if local_path.lower() in meta['path'].lower() and local_path.lower() != remote_path.lower():
            remote_path_map = True
            if meta['debug']:
                console.print("Remote path mapping found!")
                console.print(f"Local path: {local_path}")
                console.print(f"Remote path: {remote_path}")

        torrents = qbt_client.torrents.info()
        for torrent in torrents:
            try:
                torrent_path = torrent.get('content_path', f"{torrent.save_path}{torrent.name}")
                # console.print("Trying torrent_paths")
            except AttributeError:
                if meta['debug']:
                    console.print(torrent)
                    console.print_exception()
                continue
            if remote_path_map:
                # Replace remote path with local path only if not already mapped
                if not torrent_path.startswith(local_path):
                    torrent_path = torrent_path.replace(remote_path, local_path)
                    if meta['debug']:
                        console.print("Replaced paths round 2:", torrent_path)

                # Check if the local path was accidentally duplicated and correct it
                if torrent_path.startswith(f"{local_path}/{local_path.split('/')[-1]}"):
                    torrent_path = torrent_path.replace(f"{local_path}/{local_path.split('/')[-1]}", local_path)
                    if meta['debug']:
                        console.print("Corrected duplicate in torrent path round 2:", torrent_path)

                # Standardize path separators for the local OS
                torrent_path = torrent_path.replace(os.sep, '/').replace('/', os.sep)
                if meta['debug']:
                    console.print("Final torrent path after remote mapping round 2:", torrent_path)

            if meta['is_disc'] in ("", None) and len(meta['filelist']) == 1:
                if torrent_path.lower() == meta['filelist'][0].lower() and len(torrent.files) == len(meta['filelist']):
                    valid, torrent_path = await self.is_valid_torrent(meta, f"{torrent_storage_dir}/{torrent.hash}.torrent", torrent.hash, 'qbit', print_err=False)
                    if valid:
                        console.print(f"[green]Found a matching .torrent with hash: [bold yellow]{torrent.hash}")
                        return torrent.hash

            elif os.path.normpath(meta['path']).lower() == os.path.normpath(torrent_path).lower():
                valid, torrent_path = await self.is_valid_torrent(meta, f"{torrent_storage_dir}/{torrent.hash}.torrent", torrent.hash, 'qbit', print_err=False)
                if valid:
                    console.print(f"[green]Found a matching .torrent with hash: [bold yellow]{torrent.hash}")
                    return torrent.hash
        return None

    def rtorrent(self, path, torrent_path, torrent, meta, local_path, remote_path, client):
        rtorrent = xmlrpc.client.Server(client['rtorrent_url'], context=ssl._create_stdlib_context())
        metainfo = bencode.bread(torrent_path)
        try:
            fast_resume = self.add_fast_resume(metainfo, path, torrent)
        except EnvironmentError as exc:
            console.print("[red]Error making fast-resume data (%s)" % (exc,))
            raise

        new_meta = bencode.bencode(fast_resume)
        if new_meta != metainfo:
            fr_file = torrent_path.replace('.torrent', '-resume.torrent')
            console.print("Creating fast resume")
            bencode.bwrite(fast_resume, fr_file)

        isdir = os.path.isdir(path)
        # if meta['type'] == "DISC":
        #     path = os.path.dirname(path)
        # Remote path mount
        modified_fr = False
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path_dir = os.path.dirname(path)
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')
            shutil.copy(fr_file, f"{path_dir}/fr.torrent")
            fr_file = f"{os.path.dirname(path)}/fr.torrent"
            modified_fr = True
        if isdir is False:
            path = os.path.dirname(path)

        console.print("[bold yellow]Adding and starting torrent")
        rtorrent.load.start_verbose('', fr_file, f"d.directory_base.set={path}")
        time.sleep(1)
        # Add labels
        if client.get('rtorrent_label', None) is not None:
            rtorrent.d.custom1.set(torrent.infohash, client['rtorrent_label'])
        if meta.get('rtorrent_label') is not None:
            rtorrent.d.custom1.set(torrent.infohash, meta['rtorrent_label'])

        # Delete modified fr_file location
        if modified_fr:
            os.remove(f"{path_dir}/fr.torrent")
        if meta['debug']:
            console.print(f"[cyan]Path: {path}")
        return

    async def qbittorrent(self, path, torrent, local_path, remote_path, client, is_disc, filelist, meta):
        # Remote path mount
        if meta.get('keep_folder'):
            # Keep only the root folder (e.g., "D:\\Movies")
            path = os.path.dirname(path)
        else:
            # Adjust path based on filelist and directory status
            isdir = os.path.isdir(path)
            if len(filelist) != 1 or not isdir:
                path = os.path.dirname(path)

        # Ensure remote path replacement and normalization
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')

        # Ensure trailing slash for qBittorrent
        if not path.endswith('/'):
            path += '/'

        # Initialize qBittorrent client
        qbt_client = qbittorrentapi.Client(
            host=client['qbit_url'],
            port=client['qbit_port'],
            username=client['qbit_user'],
            password=client['qbit_pass'],
            VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
        )
        console.print("[bold yellow]Adding and rechecking torrent")

        try:
            qbt_client.auth_log_in()
        except qbittorrentapi.LoginFailed:
            console.print("[bold red]INCORRECT QBIT LOGIN CREDENTIALS")
            return

        # Check for automatic management
        auto_management = False
        am_config = client.get('automatic_management_paths', '')
        if isinstance(am_config, list):
            for each in am_config:
                if os.path.normpath(each).lower() in os.path.normpath(path).lower():
                    auto_management = True
        else:
            if os.path.normpath(am_config).lower() in os.path.normpath(path).lower() and am_config.strip() != "":
                auto_management = True
        qbt_category = client.get("qbit_cat") if not meta.get("qbit_cat") else meta.get('qbit_cat')
        content_layout = client.get('content_layout', 'Original')

        # Add the torrent
        try:
            qbt_client.torrents_add(
                torrent_files=torrent.dump(),
                save_path=path,
                use_auto_torrent_management=auto_management,
                is_skip_checking=True,
                content_layout=content_layout,
                category=qbt_category
            )
        except qbittorrentapi.APIConnectionError as e:
            console.print(f"[red]Failed to add torrent: {e}")
            return

        # Wait for torrent to be added
        timeout = 30
        for _ in range(timeout):
            if len(qbt_client.torrents_info(torrent_hashes=torrent.infohash)) > 0:
                break
            await asyncio.sleep(1)
        else:
            console.print("[red]Torrent addition timed out.")
            return

        # Resume and tag torrent
        qbt_client.torrents_resume(torrent.infohash)
        if client.get('qbit_tag'):
            qbt_client.torrents_add_tags(tags=client['qbit_tag'], torrent_hashes=torrent.infohash)
        if meta.get('qbit_tag'):
            qbt_client.torrents_add_tags(tags=meta['qbit_tag'], torrent_hashes=torrent.infohash)

        console.print(f"Added to: {path}")

    def deluge(self, path, torrent_path, torrent, local_path, remote_path, client, meta):
        client = DelugeRPCClient(client['deluge_url'], int(client['deluge_port']), client['deluge_user'], client['deluge_pass'])
        # client = LocalDelugeRPCClient()
        client.connect()
        if client.connected is True:
            console.print("Connected to Deluge")
            isdir = os.path.isdir(path)  # noqa F841
            # Remote path mount
            if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
                path = path.replace(local_path, remote_path)
                path = path.replace(os.sep, '/')

            path = os.path.dirname(path)

            client.call('core.add_torrent_file', torrent_path, base64.b64encode(torrent.dump()), {'download_location': path, 'seed_mode': True})
            if meta['debug']:
                console.print(f"[cyan]Path: {path}")
        else:
            console.print("[bold red]Unable to connect to deluge")

    def add_fast_resume(self, metainfo, datapath, torrent):
        """ Add fast resume data to a metafile dict.
        """
        # Get list of files
        files = metainfo["info"].get("files", None)
        single = files is None
        if single:
            if os.path.isdir(datapath):
                datapath = os.path.join(datapath, metainfo["info"]["name"])
            files = [Bunch(
                path=[os.path.abspath(datapath)],
                length=metainfo["info"]["length"],
            )]

        # Prepare resume data
        resume = metainfo.setdefault("libtorrent_resume", {})
        resume["bitfield"] = len(metainfo["info"]["pieces"]) // 20
        resume["files"] = []
        piece_length = metainfo["info"]["piece length"]
        offset = 0

        for fileinfo in files:
            # Get the path into the filesystem
            filepath = os.sep.join(fileinfo["path"])
            if not single:
                filepath = os.path.join(datapath, filepath.strip(os.sep))

            # Check file size
            if os.path.getsize(filepath) != fileinfo["length"]:
                raise OSError(errno.EINVAL, "File size mismatch for %r [is %d, expected %d]" % (
                    filepath, os.path.getsize(filepath), fileinfo["length"],
                ))

            # Add resume data for this file
            resume["files"].append(dict(
                priority=1,
                mtime=int(os.path.getmtime(filepath)),
                completed=(
                    (offset + fileinfo["length"] + piece_length - 1) // piece_length -
                    offset // piece_length
                ),
            ))
            offset += fileinfo["length"]

        return metainfo

    async def remote_path_map(self, meta):
        if meta.get('client', None) is None:
            torrent_client = self.config['DEFAULT']['default_torrent_client']
        else:
            torrent_client = meta['client']
        local_path = list_local_path = self.config['TORRENT_CLIENTS'][torrent_client].get('local_path', '/LocalPath')
        remote_path = list_remote_path = self.config['TORRENT_CLIENTS'][torrent_client].get('remote_path', '/RemotePath')
        if isinstance(local_path, list):
            for i in range(len(local_path)):
                if os.path.normpath(local_path[i]).lower() in meta['path'].lower():
                    list_local_path = local_path[i]
                    list_remote_path = remote_path[i]

        local_path = os.path.normpath(list_local_path)
        remote_path = os.path.normpath(list_remote_path)
        if local_path.endswith(os.sep):
            remote_path = remote_path + os.sep

        return local_path, remote_path

    async def get_ptp_from_hash(self, meta):
        default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        qbt_client = qbittorrentapi.Client(
            host=client['qbit_url'],
            port=client['qbit_port'],
            username=client['qbit_user'],
            password=client['qbit_pass'],
            VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
        )

        try:
            qbt_client.auth_log_in()
        except qbittorrentapi.LoginFailed as e:
            console.print(f"[bold red]Login failed while trying to get info hash: {e}")
            exit(1)

        info_hash_v1 = meta.get('infohash')
        torrents = qbt_client.torrents_info()
        found = False

        for torrent in torrents:
            if torrent.get('infohash_v1') == info_hash_v1:
                comment = torrent.get('comment', "")

                if "https://passthepopcorn.me" in comment:
                    match = re.search(r'torrentid=(\d+)', comment)
                    if match:
                        meta['ptp'] = match.group(1)
                        console.print(f"[bold cyan]meta['ptp'] set to torrentid: {meta['ptp']}")

                elif "https://aither.cc" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['aither'] = match.group(1)
                        console.print(f"[bold cyan]meta['aither'] set to ID: {meta['aither']}")

                elif "https://lst.gg" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['lst'] = match.group(1)
                        console.print(f"[bold cyan]meta['lst'] set to ID: {meta['lst']}")

                elif "https://onlyencodes.cc" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['oe'] = match.group(1)
                        console.print(f"[bold cyan]meta['oe'] set to ID: {meta['oe']}")

                elif "https://blutopia.cc" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['blu'] = match.group(1)
                        console.print(f"[bold cyan]meta['blu'] set to ID: {meta['blu']}")

                found = True
                break

        if not found:
            console.print("[bold red]Torrent with the specified infohash_v1 not found.")

        return meta