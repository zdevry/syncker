#!/usr/bin/env python3

import json
from os import getenv
from pathlib import Path
from argparse import ArgumentParser
from sys import exit
from googleapiclient.errors import HttpError

import oauth
import gdrive

def create_default_index_file(index_file_path):
    default_index = {
      'drive_files': {
        '__gdrive_id': 'root',
        '__gdrive_folder': True
      },
      'links': {}
    }
    with open(index_file_path, 'w') as f:
        json.dump(default_index, f, indent=2)
    return default_index

def load_index_file(index_file_path):
    if not Path.exists(index_file_path):
        return create_default_index_file(index_file_path)
    with open(index_file_path) as f:
        return json.load(f)

def save_index_file(index, index_file_path):
    with open(index_file_path, 'w') as f:
        return json.dump(index, f, indent=2)

def parse_args():
    p = ArgumentParser(description=
        'Sync files in Google Drive. All Drive paths are specified as "gdrive:/path/to/file" '
        '(forward slashes \'/\' only)')

    sp = p.add_subparsers(required=True)

    auth_sp = sp.add_parser('auth', help='Perform OAuth2 Authentication')
    auth_sp.set_defaults(subcmd='auth')

    list_sp = sp.add_parser('list', help='List indexed Drive files')
    list_sp.set_defaults(subcmd='list')
    list_sp.add_argument('--no-tree', '-l', action='store_true',
        help='List each index file as its full path on individual lines')
    list_sp.add_argument('--hide-links', '-u', action='store_true',
        help='Do not show linked local files')

    index_sp = sp.add_parser('index', help='Add a Drive file to the local index')
    index_sp.set_defaults(subcmd='index')
    index_sp.add_argument('drive_file', help='The Drive file to index')

    unindex_sp = sp.add_parser('unindex', help='Remove a Drive file from the local index')
    unindex_sp.set_defaults(subcmd='unindex')
    unindex_sp.add_argument('drive_file', help='The Drive file to unindex')

    link_sp = sp.add_parser('link', help='Link a local file to an indexed Drive file for syncing')
    link_sp.set_defaults(subcmd='link')
    link_sp.add_argument('drive_file', help='The Drive file to link')
    link_sp.add_argument('local_file', help='The local file to link')

    unlink_sp = sp.add_parser('unlink', help='Unlink a local file from an indexed Drive file')
    unlink_sp.set_defaults(subcmd='unlink')
    unlink_sp.add_argument('file', help='The local or Drive file to unlink from each other')

    sync_sp = sp.add_parser('sync',
        help='Update an indexed Drive file with the contents of its linked local file')
    sync_sp.set_defaults(subcmd='sync')
    sync_sp.add_argument('file', help='The local or Drive file to sync with each other')

    backup_sp = sp.add_parser('backup',
        help='Create a backup copy of an indexed Drive file in its parent folder')
    backup_sp.set_defaults(subcmd='backup')
    backup_sp.add_argument('drive_file', help='The Drive file to backup')
    backup_sp.add_argument('--name', '-n', required=False,
        help='The name of the backup, defaults to "YYYYmmDD-HHMMSS-BACKUP-filename.ext"')

    download_sp = sp.add_parser('download', help='Download an indexed Drive file')
    download_sp.set_defaults(subcmd='download')
    download_sp.add_argument('drive_file', help='The Drive file to download')
    download_sp.add_argument('--to', '-o', required=False,
        help='Location to download the file, defaults to ./filename.ext')

    update_sp = sp.add_parser('update',
        help='Update an indexed Drive file with the contents of a specified local file')
    update_sp.set_defaults(subcmd='update')
    update_sp.add_argument('drive_file', help='The Drive file to update')
    update_sp.add_argument('local_file', help='The source local file')

    upload_sp = sp.add_parser('upload',
        help='Upload a local file to an indexed Drive folder, then add the file to the local index')
    upload_sp.set_defaults(subcmd='upload')
    upload_sp.add_argument('local_file', help='The local file to upload')
    upload_sp.add_argument('drive_folder', help='The target parent Drive folder')
    upload_sp.add_argument('--name', '-n', required=False,
        help='The name of the uploaded Drive file')
    upload_sp.add_argument('--no-index', '-x', action='store_true',
        help='Skip indexing the uploaded file')

    return p.parse_args()

def main():
    try:
        args = parse_args()

        syncker_dir_env = getenv('SYNCKER_DIR')
        syncker_dir = Path(syncker_dir_env) if syncker_dir_env \
            else (Path.home() / '.config' / 'syncker')
        if not Path.exists(syncker_dir):
            Path.mkdir(syncker_dir)
        else:
            if not Path.is_dir(syncker_dir):
                raise FileExistsError(f'SYNCKER_DIR ({syncker_dir}) already exists but is not a directory')

        if args.subcmd == 'auth':
            oauth.authenticate(syncker_dir)
            return

        index_file = syncker_dir / 'index.json'
        index = load_index_file(index_file)

        match args.subcmd:
            case 'list':
                if args.no_tree:
                    gdrive.list_index_lines(index['drive_files'], hide_links=args.hide_links)
                else:
                    gdrive.list_index_tree(index['drive_files'], hide_links=args.hide_links)
                return
            case 'unindex':
                gdrive.unindex(args.drive_file, index)
                save_index_file(index, index_file)
                return
            case 'link':
                gdrive.link_index(args.drive_file, args.local_file, index)
                save_index_file(index, index_file)
                return
            case 'unlink':
                gdrive.unlink_index(args.file, index)
                save_index_file(index, index_file)
                return

        creds = oauth.get_credentials(syncker_dir)
        service = gdrive.get_service(creds)

        match args.subcmd:
            case 'index':
                gdrive.index(service, args.drive_file, index['drive_files'])
                save_index_file(index, index_file)
            case 'sync':
                gdrive.sync_index(service, args.file, index)
            case 'backup':
                gdrive.backup_index(service, args.drive_file, index['drive_files'], filename=args.name)
            case 'download':
                gdrive.download_index(service, args.drive_file, index['drive_files'], download_file_path=args.to)
            case 'update':
                gdrive.update_direct(service, args.drive_file, args.local_file, index['drive_files'])
            case 'upload':
                gdrive.upload_and_index(service, args.drive_folder, args.local_file, index, filename=args.name, no_index=args.no_index)
                save_index_file(index, index_file)
    except oauth.AuthenticationError as err:
        print('Error in authentication:', err)
        exit(1)
    except gdrive.DrivePathError as err:
        print('Drive path error:', err)
        exit(1)
    except FileExistsError as err:
        print('File error:', err)
    except FileNotFoundError as err:
        print('File error:', err)
    except HttpError as err:
        print('API error:', err)

if __name__ == '__main__':
        main()
