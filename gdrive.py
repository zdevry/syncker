import os
from io import FileIO
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

class DrivePathError(Exception):
    pass

def shorten_file_in_home(path):
    if os.name == 'nt': # Don't shorten HOME files on Windows
        return path

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

def unlink_files(f, links):
    if not f['__gdrive_folder']:
        if 'link' in f:
            link_path = f['link']
            links.pop(link_path, None)
        return

    for subf in f:
        if subf == '__gdrive_id' or subf == '__gdrive_folder':
            continue
        unlink_files(f[subf], links)

def unindex(drive_file_path, index):
    folders = get_folder_seq(drive_file_path)
    if len(folders) == 0:
        raise DrivePathError(f'Cannot unindex Drive root folder')
    curr_folder_ref = index['drive_files']
    prev_folder_ref = index['drive_files']
    for f_name in folders:
        if not curr_folder_ref['__gdrive_folder']:
            raise DrivePathError(f'"{f_name}" is not a folder')
        if f_name not in curr_folder_ref:
            raise DrivePathError(f'"{drive_file_path}" (folder/file: {f_name}) is not indexed')
        prev_folder_ref = curr_folder_ref
        curr_folder_ref = curr_folder_ref[f_name]

    unlink_files(curr_folder_ref, index['links'])
    prev_folder_ref.pop(folders[-1], None)

def list_index_lines(folder, prefix='gdrive:/', hide_links=False):
    for f in folder:
        if f == '__gdrive_id' or f == '__gdrive_folder':
            continue
        subfolder = folder[f]
        if subfolder['__gdrive_folder']:
            subfolder_name = prefix + f + '/'
            print(subfolder_name)
            list_index_lines(subfolder, prefix=subfolder_name, hide_links=hide_links)
        elif 'link' in subfolder and not hide_links:
            link = shorten_file_in_home(subfolder['link'])
            print(f'{prefix}{f} [{link}]')
        else:
            print(f'{prefix}{f}')

def list_index_tree(folder, depth=0, hide_links=False):
    for f in folder:
        if f == '__gdrive_id' or f == '__gdrive_folder':
            continue
        indent_lines = '\u2502 ' * depth
        subfolder = folder[f]
        if subfolder['__gdrive_folder']:
            print(f'\x1B[90m{indent_lines}\x1B[m{f}')
            list_index_tree(subfolder, depth=depth + 1, hide_links=hide_links)
        elif 'link' in subfolder and not hide_links:
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
    abspath = os.path.abspath(local_file_path)
    links = index['links']
    if abspath in links:
        old_linked_file_path = links[abspath]
        print(f'"{local_file_path}" is already linked to "{old_linked_file_path}", replacing link...')
        old_linked_file = get_indexed(old_linked_file_path, index['drive_files'])
        old_linked_file.pop('link', None)
        links.pop(abspath, None)

    drive_index_ref = get_indexed(drive_file_path, index['drive_files'])
    if drive_index_ref['__gdrive_folder']:
        raise DrivePathError('Cannot link a folder')

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

    if not os.path.exists(local_link):
        raise FileNotFoundError(
            f'{shorten_file_in_home(local_link)} no longer exists, consider unlinking with `syncker unlink`')

    drive_path = index['links'][local_link]
    print(f'Syncing {drive_path} with {shorten_file_in_home(local_link)}')

    file_data = MediaFileUpload(local_link, resumable=True)
    service.files() \
        .update(fileId=drive_file['__gdrive_id'], media_body=file_data) \
        .execute()

def get_filename_by_id(service, id):
    return service.files().get(fileId=id).execute()['name']

def backup_index(service, drive_file_path, root_folder, filename=None):
    original_file = get_indexed(drive_file_path, root_folder)
    if original_file['__gdrive_folder']:
        raise DrivePathError('Cannot backup a folder')

    backup_filename = filename \
        or (datetime.today().strftime('BACKUP-%Y%m%d-%H%M%S-')
            + get_filename_by_id(service, original_file['__gdrive_id']))
    print(f'Backing up {drive_file_path} to {backup_filename} ...')
    service.files() \
        .copy(fileId=original_file['__gdrive_id'], body={'name': backup_filename}) \
        .execute()

def download_index(service, drive_file_path, root_folder, download_file_path=None):
    file = get_indexed(drive_file_path, root_folder)
    filepath = download_file_path or get_filename_by_id(service, file['__gdrive_id'])
    if os.path.exists(filepath):
        raise FileExistsError(f'{filepath} already exists')

    request = service.files().get_media(fileId=file['__gdrive_id'])
    with open(filepath, 'wb') as f:
        download = MediaIoBaseDownload(f, request)

        print('Start downloading...')
        done = False
        while not done:
            status, done = download.next_chunk()
            if status:
                percent = int(status.progress() * 100)
                print(f'Downloading {percent}%')
        print('Download complete')

def update_direct(service, drive_file_path, local_file_path, root_folder):
    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f'"{local_file_path}" does not exist')

    drive_file = get_indexed(drive_file_path, root_folder)
    print(f'Updating {drive_file_path} with {local_file_path}')

    file_data = MediaFileUpload(local_file_path, resumable=True)
    service.files() \
        .update(fileId=drive_file['__gdrive_id'], media_body=file_data) \
        .execute()

def upload_and_index(service, drive_folder_path, local_file_path, index, filename=None, no_index=False):
    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f'"{local_file_path}" does not exist')

    drive_folder = get_indexed(drive_folder_path, index['drive_files'])
    if not drive_folder['__gdrive_folder']:
        raise DrivePathError(f'"{drive_folder_path}" is not a folder')

    file_basename = filename or os.path.basename(local_file_path)
    drive_file_path = \
        drive_folder_path \
        + ('' if drive_folder_path.endswith('/') else '/') \
        + file_basename

    file_metadata = {
        'name': file_basename,
        'parents': [drive_folder['__gdrive_id']]
    }

    print(f'Uploading {local_file_path} to {drive_file_path}')

    file_data = MediaFileUpload(local_file_path, resumable=True)
    file_id = service.files() \
        .create(body=file_metadata, media_body=file_data) \
        .execute()['id']

    if no_index:
        return

    print(f'Indexing and linking {drive_file_path}')

    local_abspath = os.path.abspath(local_file_path)
    drive_folder[file_basename] = {
        '__gdrive_id': file_id,
        '__gdrive_folder': False,
        'link': local_abspath
    }
    links = index['links']
    if local_abspath in links:
        old_linked_file_path = links[local_abspath]
        print(f'"{local_file_path}" is already liinked with {old_linked_file_path}, replacing link...')
        old_linked_file = get_indexed(old_linked_file_path, index['drive_files'])
        old_linked_file.pop('link', None)
    links[local_abspath] = drive_file_path
