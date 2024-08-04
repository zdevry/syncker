import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class DrivePathError(Exception):
    pass

def shorten_file_in_home(path):
    home = os.getenv('HOME')
    if path.startswith(home):
        return '~' + path.removeprefix(home)
    else:
        return path

def get_folder_seq(path):
    if not path.startswith('gdrive:/'):
        raise DrivePathError(f'"{path}" is not a Drive path')
    return [f for f in path.removeprefix('gdrive:/').split('/') if f != '']

def get_service(creds):
    return build('drive', 'v3', credentials=creds)

def index(service, drive_file_path, root_folder_ref):
    folders = get_folder_seq(drive_file_path)
    curr_file_ref = root_folder_ref
    for f_name in folders:
        if not curr_file_ref['__gdrive_folder']:
            raise DrivePathError(f'"{f_name}" is not a folder')
        curr_folder_id = curr_file_ref['__gdrive_id']

        if f_name in curr_file_ref:
            curr_file_ref = curr_file_ref[f_name]
            continue

        print('finding file', f_name)
        matched_files = service.files().list(
            q=f"'me' in owners and trashed = false and '{curr_folder_id}' in parents and name = '{f_name}'"
        ).execute()['files']

        if len(matched_files) == 0:
            raise DrivePathError(f'{drive_file_path} does not exist')
        file = matched_files[0]

        indexed_file = {
            '__gdrive_id': file['id'],
            '__gdrive_folder': file['mimeType'] == 'application/vnd.google-apps.folder'
        }
        curr_file_ref[f_name] = indexed_file
        curr_file_ref = indexed_file

def unindex(drive_file_path, root_folder_ref):
    folders = get_folder_seq(drive_file_path)
    if len(folders) == 0:
        raise DrivePathError(f'Cannot unindex Drive root folder')
    curr_folder_ref = root_folder_ref
    prev_folder_ref = root_folder_ref
    for f_name in folders:
        if not curr_folder_ref['__gdrive_folder']:
            raise DrivePathError(f'"{f_name}" is not a folder')
        if f_name not in curr_folder_ref:
            raise DrivePathError(f'"{drive_file_path}" (folder/file: {f_name}) is not indexed')
        prev_folder_ref = curr_folder_ref
        curr_folder_ref = curr_folder_ref[f_name]

    prev_folder_ref.pop(folders[-1], None)

def list_index(folder, depth=0):
    for f in folder:
        if f == '__gdrive_id' or f == '__gdrive_folder':
            continue
        indent_lines = '\u2502 ' * depth
        subfolder = folder[f]
        if subfolder['__gdrive_folder']:
            print(f'\x1B[90m{indent_lines}\x1B[m{f}')
            list_index(subfolder, depth=depth + 1)
        elif 'link' in subfolder:
            link = shorten_file_in_home(subfolder['link'])
            print(f'\x1B[90m{indent_lines}\x1B[m{f} [{link}]')
        else:
            print(f'\x1B[90m{indent_lines}\x1B[m{f}')

def get_indexed(drive_file_path, root_folder):
    folders = get_folder_seq(drive_file_path)
    curr_folder_ref = root_folder
    for f_name in folders:
        if not curr_folder_ref['__gdrive_folder']:
            raise DrivePathError(f'"{f_name}" is not a folder')
        if f_name not in curr_folder_ref:
            raise DrivePathError(f'"{drive_file_path}" (folder/file: {f_name}) is not indexed')
        curr_folder_ref = curr_folder_ref[f_name]
    return curr_folder_ref

def get_linked(path, index):
    if path.startswith('gdrive:/'):
        file = get_indexed(path, index['drive_files'])
        if 'link' not in file:
            raise DrivePathError(f'{path} is not linked with any local files')
        return file
    else:
        abspath = os.path.abspath(path)
        links = index['links']
        if abspath not in links:
            raise DrivePathError(f'{path} is not linked with any drive files')
        return get_indexed(links[abspath], index['drive_files'])

def link_index(drive_file_path, local_file_path, index):
    drive_index_ref = get_indexed(drive_file_path, index['drive_files'])
    if drive_index_ref['__gdrive_folder']:
        raise DrivePathError('Cannot link a folder')
    abspath = os.path.abspath(local_file_path)

    if 'link' in drive_index_ref:
        existing_link_path = drive_index_ref['link']
        print(f'"{drive_file_path}" already has existing link "{existing_link_path}", replacing link...')
        index['links'].pop(existing_link_path, None)

    drive_index_ref['link'] = abspath
    index['links'][abspath] = drive_file_path

def unlink_index(path, index):
    drive_file_ref = get_linked(path, index)
    index['links'].pop(drive_file_ref['link'], None)
    drive_file_ref.pop('link', None)

def sync_index(service, path, index):
    drive_file = get_linked(path, index)
    local_link = drive_file['link']

    drive_path = index['links'][local_link]
    print(f'Syncing {drive_path} with {shorten_file_in_home(local_link)}')

    file_data = MediaFileUpload(local_link)
    service.files() \
        .update(fileId=drive_file['__gdrive_id'], media_body=file_data) \
        .execute()
