## syncker

A utility I made for personal use to sync files in Google Drive with files saved locally.
Note that this is not a complete Drive client, many things still need to be done
through the web UI or another Drive client.

Only GNU/Linux tested and supported. This may work on other Unix-like OSes and Windows (see below).

## Install

Install using pipx/pip:
```
git clone https://github.com/zdevry/syncker.git
cd syncker
pipx install .

# Alternatively, install directly from the repo
# Be careful of installing random programs from the web without auditing
pipx install git+https://github.com/zdevry/syncker.git
```

Dependencies required to run the script directly:
```
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Setup

`syncker` puts its files in `~/.config/syncker/` by default but can be changed
by setting the `SYNCKER_DIR` environment variable.
This may be important for OSes where the default location is not the conventional
location to store configuration (namely Windows).

The program requires authentication through OAuth2 to use the Google Drive API.
Since I'm not providing API keys for this, you need to create your own keys.
Refer to [Configure OAuth Consent](https://developers.google.com/workspace/guides/configure-oauth-consent)
and [Python quickstart](https://developers.google.com/drive/api/quickstart/python)
for more info. Place the newly created client secrets into `$SYNCKER_DIR/client_secrets.json`,
then run `syncker auth` to perform authentication.

## Usage

For help with usage:
```
syncker --help
```

Example of a basic workflow
```
# index a folder in Google Drive so it can be accessed
syncker index gdrive:/Projects

# upload a file to the folder and track/index it
syncker upload Thesis.tex gdrive:/Projects

# update the file in Google Drive with new file contents
syncker sync gdrive:/Projects/Thesis.tex

# create a backup of the file by creating a copy in the same Drive folder
syncker backup gdrive:/Projects/Thesis.tex

# Local file paths can also be used to sync since the app keeps track of that
syncker sync /path/to/Thesis.tex
```
