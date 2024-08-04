#!/usr/bin/env python3

import json
import os.path
from argparse import ArgumentParser
from sys import exit

import oauth
import gdrive

CONFIG_DIR = '.private'

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

def load_index_file():
    index_file_path = CONFIG_DIR + '/index.json'
    if not os.path.exists(index_file_path):
        return create_default_index_file(index_file_path)
    with open(index_file_path) as f:
        return json.load(f)

def save_index_file(index):
    index_file_path = CONFIG_DIR + '/index.json'
    with open(index_file_path, 'w') as f:
        return json.dump(index, f, indent=2)

def parse_args():
    p = ArgumentParser()

    sp = p.add_subparsers(required=True)

    auth_sp = sp.add_parser('auth')
    auth_sp.set_defaults(subcmd='auth')

    auth_sp = sp.add_parser('list')
    auth_sp.set_defaults(subcmd='list')

    index_sp = sp.add_parser('index')
    index_sp.set_defaults(subcmd='index')
    index_sp.add_argument('index_file')

    unindex_sp = sp.add_parser('unindex')
    unindex_sp.set_defaults(subcmd='unindex')
    unindex_sp.add_argument('unindex_file')

    link_sp = sp.add_parser('link')
    link_sp.set_defaults(subcmd='link')
    link_sp.add_argument('drive_file')
    link_sp.add_argument('local_file')

    unlink_sp = sp.add_parser('unlink')
    unlink_sp.set_defaults(subcmd='unlink')
    unlink_sp.add_argument('file')

    sync_sp = sp.add_parser('sync')
    sync_sp.set_defaults(subcmd='sync')
    sync_sp.add_argument('file')

    return p.parse_args()

def main():
    args = parse_args()

    if args.subcmd == 'auth':
        oauth.authenticate(CONFIG_DIR)
        return

    index = load_index_file()

    match args.subcmd:
        case 'list':
            gdrive.list_index(index['drive_files'])
            return
        case 'unindex':
            gdrive.unindex(args.unindex_file, index['drive_files'])
            save_index_file(index)
            return
        case 'link':
            gdrive.link_index(args.drive_file, args.local_file, index)
            save_index_file(index)
            return
        case 'unlink':
            gdrive.unlink_index(args.file, index)
            save_index_file(index)
            return

    creds = oauth.get_credentials(CONFIG_DIR)
    service = gdrive.get_service(creds)

    match args.subcmd:
        case 'index':
            gdrive.index(service, args.index_file, index['drive_files'])
            save_index_file(index)
        case 'sync':
            gdrive.sync_index(service, args.file, index)

if __name__ == '__main__':
    try:
        main()
    except oauth.AuthenticationError as err:
        print('Error in authentication:', err)
        exit(1)
    except gdrive.DrivePathError as err:
        print('Drive path error:', err)
        exit(1)
