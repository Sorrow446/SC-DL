# SC-DL
Tool written in Python to download tracks from SoundCloud.
![](https://i.imgur.com/CwTqTGd_d.png?maxwidth=760)    
First build. Please report any issues.
[Windows binaries](https://github.com/Sorrow446/SC-DL/releases)

## Supported Media
|Type|URL example|
| --- | --- |
|Album/playlist|`https://soundcloud.com/x/sets/x`
|Artist albums|`https://soundcloud.com/x/albums`
|Artist tracks|`https://soundcloud.com/x/tracks`
|Track|`https://soundcloud.com/x/x https://soundcloud.com/x/x?in=x/sets/x`
|User likes|`https://soundcloud.com/you/likes`

## Setup
1. Put [FFmpeg binary (win64, gpl)](https://github.com/BtbN/FFmpeg-Builds/releases) in SC-DL's folder.
2. Fill in `config.json` (any specified CLI arguments will override these).
3. Dump cookies using chrome_cookies.py/chrome_cookies_x86.exe for Chrome or firefox_cookies.py/firefox_cookies_x86.exe for Firefox (login first). You can also use a browser extension such as [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) (cookies file must be named "cookies.txt" and in Netscape format).
4. Call it with your args via Command Prompt. `sc-dl.py/sc-dl_x86.exe -u <media url>`

## Usage Examples
Download a single track.    
`sc-dl.py/sc-dl_x86.exe -u https://soundcloud.com/pauloakenfold/paul-oakenfold-tranceport`

Download all user albums.    
`sc-dl.py/sc-dl_x86.exe -u https://soundcloud.com/pauloakenfold/albums`

Download from two lists and all user likes.    
`sc-dl.py/sc-dl_x86.exe -u E:/urls.txt E:/urls_2.txt https://soundcloud.com/you/likes`

You can mix all media types. Duplicate URLs and text files will be filtered.

```
 _____ _____     ____  __
|   __|     |___|    \|  |
|__   |   --|___|  |  |  |__
|_____|_____|   |____/|_____|

usage: sc-dl.py [-h] -u URLS [URLS ...] [-q {1,2,3,4}] [-o OUTPUT_PATH] [-t TEMPLATE] [-k]

optional arguments:
  -h, --help            show this help message and exit
  -u URLS [URLS ...], --urls URLS [URLS ...]
                        Multiple links or text file filenames / paths.
  -q {1,2,3,4}, --quality {1,2,3,4}
                        1: 64kbps Opus, 2: 128 Kbps MP3, 3: 256 Kbps AAC, 4: best/download.
  -o OUTPUT_PATH, --output-path OUTPUT_PATH
                        Output path. Double up backslashes or use single forward slashes for Windows.
  -t TEMPLATE, --template TEMPLATE
                        Naming template for track filenames.
  -k, --keep-cover      Keep cover in album folder.
```
