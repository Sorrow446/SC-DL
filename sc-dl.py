import os
import re
import sys
import json
import base64
import argparse
import platform
import traceback
import subprocess

import m3u8
import mutagen
import requests
from tqdm import tqdm
from mutagen import id3
from mutagen.flac import Picture
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3NoHeaderError

from api import client


def err(msg):
	print(msg)
	traceback.print_exc()

def parse_cfg():
	with open('config.json', encoding='UTF-8') as f:
		return json.load(f)

def parse_cookies():
	parsed = {}
	with open('cookies.txt', encoding='UTF-8') as f:
		lines = f.readlines()
	for line in lines:
		if line.startswith('#'):
			continue
		split_line = line.split('\t')
		parsed[split_line[-2]] = split_line[-1].rstrip('\n').replace('&amp;', '&').replace('&quot;', '"')
	return parsed

def dir_setup(path):
	if not os.path.isdir(path):
		os.makedirs(path)

def read_txt(path):
	with open(path) as f:
		return [u.strip() for u in f.readlines() if u.strip()]

def process_urls(urls):
	processed = []
	fix = lambda x: x.split('#')[0]
	for url in urls:
		if url.endswith('.txt'):
			for txt_url in read_txt(url):
				if txt_url not in processed:
					processed.append(fix(txt_url))
		else:
			if url not in processed:
				processed.append(fix(url))
	return processed

def parse_prefs():
	cfg = parse_cfg()
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-u', '--urls', 
		nargs='+', required=True,
		help='Multiple links or text file filenames / paths.'
	)
	parser.add_argument(
		'-q', '--quality',
		choices=[1, 2, 3, 4], default=cfg['quality'], type=int,
		help='1: 64kbps Opus, 2: 128 Kbps MP3, 3: 256 Kbps AAC, 4: best/download.'
	)
	parser.add_argument(
		'-o', '--output-path',
		default=cfg['output_path'],
		help='Output path. Double up backslashes or use single '
			 'forward slashes for Windows.'
	)
	parser.add_argument(
		'-t', '--template',
		default=cfg['fname_template'],
		help='Naming template for track filenames.'
	)
	parser.add_argument(
		'-k', '--keep-cover', 
		action='store_true', default=cfg['keep_cover'],
		help='Keep cover in album folder.'
	)
	args = vars(parser.parse_args())
	cfg.update(args)
	cfg['urls'] = process_urls(cfg['urls'])
	return cfg

def check_url(url):
	media_types = [
		(r'^https://soundcloud.com/[\w-]+/sets/[\w-]+$', 'set'),
		(r'^https://soundcloud.com/you/likes$', 'likes'),
		(r'^https://soundcloud.com/[\w-]+/albums$', 'albums'),
		(r'^https://soundcloud.com/[\w-]+/tracks$', 'tracks'),
		(r'^https://soundcloud.com/[\w-]+/[\w-]+$', 'track'),
		(r'^https://soundcloud.com/[\w-]+/[\w-]+\?in=[\w-]+/sets/[\w-]+$', 'track')
	]
	for media_type in media_types:
		if re.match(media_type[0], url) != None:
			return media_type[1]

def sanitize(fname):
	if is_win:
		return re.sub(r'[\/:*?"><|]', '_', fname)
	else:
		return re.sub('/', '_', fname)			

def parse_template(meta, unparsed, default):
	try:
		parsed = unparsed.format(**meta)
	except KeyError:
		print('Failed to parse template. Default one will be used instead.')
		parsed = default.format(**meta)
	return sanitize(parsed)

def parse_meta(src, meta=None, num=None, total=None, url=None):
	if meta != None:
		year = src.get('release_date')
		if year != None:
			year = year.split('-')[0]
		meta['artist'] = src['user']['username']
		meta['title'] =	 src.get('title')
		meta['tracknumber'] = num
		meta['trackpadded'] = str(num).zfill(len(str(meta['tracktotal'])))
		meta['year'] = year
		if src.get('publisher_metadata') != None:
			meta['isrc'] = src['publisher_metadata'].get('isrc')
			meta['upc'] = src['publisher_metadata'].get('upc_or_ean')
			meta['artist'] = src['publisher_metadata'].get('artist')
	else:
		meta = {
			'album': src['title'],
			'albumartist': src['user']['username'], 
			'comment': src['permalink_url'],
			'genre': src.get('genre'),
			'tracktotal': total
		}
		if src.get('publisher_metadata') != None:
			meta['copyright'] = src.get('c_line')
	return meta

# mp3 always available?
def query_quals(meta):
	specs = {
		'audio/ogg': ['64 Kbps OPUS', '.ogg'],
		'audio/mpeg': ['128 Kbps MP3', '.mp3'],
		'audio/mp4': ['256 Kbps AAC', '.m4a'],
		'download': []
	}
	for transcode in meta['media']['transcodings']:
		if transcode['format']['protocol'] == 'hls':
			mime_key = transcode['format']['mime_type'].split(';')[0]
			specs[mime_key].append(transcode['url'])
	want = cfg['quality']
	if want == 4:
		if meta['downloadable'] == True and meta['has_downloads_left'] == True:
			key = 'download'
			specs[key].extend(client.get_file(specs[key][0]))			
		elif len(specs['audio/mp4']) == 3:
			key = 'audio/mp4'
		else:
			key = 'audio/mpeg'
	elif want == 3:
		if len(specs['audio/mp4']) == 3:
			key = 'audio/mp4'
		else:
			key = 'audio/mpeg'
	elif want == 2:
		key = 'audio/mpeg'
	elif want == 1:	
		if len(specs['audio/ogg']) == 3:
			key = 'audio/ogg'
		else:
			raise Exception('Unavailable in OPUS.')
	return specs[key]

def download_seg(url, path):
	segments = []
	manifest = client.get_manifest(url)
	parsed = m3u8.loads(manifest)
	if parsed.segment_map != None:
		segments = [parsed.segment_map['uri']]
	segments.extend(x.uri for x in parsed.segments)
	out_path = os.path.join('sc-dl_tmp', 'tmp.mp4')
	with tqdm(total=len(segments), 
		bar_format='{l_bar}{bar}{n_fmt}/{total_fmt} segments [{elapsed}<{remaining}]') as bar:
				   
		with open(out_path, 'wb') as f:
			for url in segments:
				r = requests.get(url, headers={'Range': 'bytes=0-'}, stream=True)
				r.raise_for_status()
				for chunk in r.iter_content(32*1024):
					if chunk:
						f.write(chunk)
				bar.update(1)
	subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', out_path, '-c:a', 'copy', path])

def download(url, path):
	out_path = os.path.join('sc-dl_tmp', 'tmp.mp4')
	r = requests.get(url, headers={'Range': 'bytes=0-'}, stream=True)
	r.raise_for_status()
	with tqdm(total=int(r.headers['Content-Length']), unit='B', unit_scale=True,
		unit_divisor=1024) as bar:
		with open(out_path, 'wb') as f:
			for chunk in r.iter_content(32*1024):
				if chunk:
					f.write(chunk)
					bar.update(len(chunk))

def write_tags(meta, path, ext, cov_path):
	if cov_path != None:
		with open(cov_path, 'rb') as f:
			cov_data = f.read()
	if ext == '.m4a':
		t = [
			('\xa9alb', 'album'),
			('aART', 'albumartist'),
			('\xa9ART', 'artist'),
			('\xa9cmt', 'comment'),
			('\xa9gen', 'genre'),
			('\xa9nam', 'title'),
			('\xa9day', 'year')
		]
		audio = MP4(path)
		audio.delete()
		for frame, key in t:
			if meta.get(key):
				audio[frame] = meta[key]
		audio['trkn'] = [(meta['tracknumber'], meta['tracktotal'])]
		if cov_path != None:
			audio['covr'] = [MP4Cover(cov_data, imageformat=MP4Cover.FORMAT_JPEG)]
	if ext == '.mp3':
		try: 
			audio = id3.ID3(path)
		except ID3NoHeaderError:
			audio = id3.ID3()
		audio['TRCK'] = id3.TRCK(
			encoding=3, text="{}/{}".format(meta['tracknumber'], meta['tracktotal'])
		)
		legend={
			'album': id3.TALB,
			'albumartist': id3.TPE2,
			'artist': id3.TPE1,
			'comment': id3.COMM,
			'copyright': id3.TCOP,
			'isrc': id3.TSRC,
			'label': id3.TPUB,
			'title': id3.TIT2,
			'year': id3.TYER
		}
		for k, v in meta.items():
			id3tag = legend.get(k)
			if v and id3tag:
				audio[id3tag.__name__] = id3tag(encoding=3, text=v)
		if cov_path != None:
			audio.add(id3.APIC(3, 'image/jpeg', 3, None, cov_data))
	elif ext == '.ogg':
		audio = OggOpus(path)
		del meta['trackpadded']
		for k, v in meta.items():
			if v:
				audio.tags[k] = str(v)
		if cov_path != None:
			picture = Picture()
			picture.data = cov_data
			picture.type = 17
			picture.mime = u'image/jpeg'
			picture.width = 500
			picture.height = 500
			picture.depth = 16
			picture_data = picture.write()
			encoded_data = base64.b64encode(picture_data)
			vcomment_value = encoded_data.decode('ascii')
			audio['metadata_block_picture'] = [vcomment_value]
	audio.save(path)

def write_cover(path, url):
	cov_path = os.path.join(path, 'cover.jpg')
	url = url[:-9] + 't500x500.jpg'
	r = requests.get(url)
	r.raise_for_status()
	with open(cov_path, 'wb') as f:
		f.write(r.content)
	return cov_path

def is_downloadable(track):
	if track['streamable'] == False:
		print('Track is not streamable.')
		return False
	elif track['monetization_model'] == 'SUB_HIGH_TIER' and is_go_plus == False:
		print('Track requires an active Go+ subscription.')
		return False
	elif track['policy'] == 'BLOCK':
		print('Track unavailable in your region.')
		return False
	return True

def get_additional_meta(_url):
	split = _url.split('?in=')
	url = 'https://soundcloud.com/' + split[-1]
	meta = client.get_metadata(url)['tracks']
	total = len(meta)
	for num, _track in enumerate(meta, 1):
		if _track.get('permalink_url') == split[0]:
			return num, total	

def iter_track(meta, path, parsed_meta, num_oride=-1):
	cov_path = None
	out_path = os.path.join('sc-dl_tmp', 'tmp.mp4')
	total = len(meta)
	for num, track in enumerate(meta, 1):
		if is_downloadable(track) == False:
			continue
		if num_oride != -1:
			parsed_meta = parse_meta(track, meta=parsed_meta, num=num_oride)
		else:
			parsed_meta = parse_meta(track, meta=parsed_meta, num=num)
		specs = query_quals(track)
		is_dload = specs[2].startswith('https://c')
		if num == 1 and is_dload == False:
			try:
				cov_path = write_cover(path, meta[0]['artwork_url'])
			except Exception:
				print('Failed to write cover.')
		template = parse_template(parsed_meta, cfg['template'], '{trackpadded}. {title}')
		ffmpeg_out_path = os.path.join(path, str(num)) + specs[1]
		post_path = os.path.join(path, template) + specs[1]
		if os.path.isfile(post_path):
			print('Track already exists locally.')
			continue	
		if is_dload == True:
			print('Downloading track {} of {}: {} - {} (download button)'.format(num, total, parsed_meta['title'], specs[0]))
			download(specs[2], ffmpeg_out_path)
		else:
			print('Downloading track {} of {}: {} - {}'.format(num, total, parsed_meta['title'], specs[0]))
			download_seg(specs[2], ffmpeg_out_path)
			write_tags(parsed_meta, ffmpeg_out_path, specs[1], cov_path)
		try:
			os.rename(ffmpeg_out_path, post_path)
		except Exception:
			print('Failed to rename track.')
	if cov_path != None and cfg['keep_cover'] == False:
		os.remove(cov_path)

def set(meta, _, path=None):
	parsed_meta = parse_meta(meta, total=len(meta['tracks']))
	template = parse_template(parsed_meta, 
		cfg['media_types']['set']['folder_template'], '{albumartist} - {album}')
	album_folder = "{} - {}".format(parsed_meta['albumartist'], parsed_meta['album'])
	if path != None:
		album_path = os.path.join(path, template)
	else:
		album_path = os.path.join(cfg['output_path'], template)
	dir_setup(album_path)
	print(album_folder)
	iter_track(meta['tracks'], album_path, parsed_meta)

def track(meta, url, path=None, num=1, total=1):
	if '?in=' in url:
		num, total = get_additional_meta(url)
	parsed_meta = parse_meta(meta, total=total)
	template = parse_template(parsed_meta, 
		cfg['media_types']['track']['folder_template'], '{albumartist} - {album}')
	track_folder = "{} - {}".format(parsed_meta['albumartist'], meta['title'])
	if path != None:
		track_path = os.path.join(path, template)
	else:
		track_path = os.path.join(cfg['output_path'], template)
	print(track_folder)
	dir_setup(track_path)
	iter_track([meta], track_path, parsed_meta, num_oride=num)

def albums(artist_meta, _):
	total = 0
	template = parse_template(artist_meta, 
		cfg['media_types']['artist_albums']['folder_template'], '{username}')	
	artist_path = os.path.join(cfg['output_path'], template)
	print(artist_meta['username'] + '\'s albums')
	dir_setup(artist_path)
	albums = client.get_artist_albums(str(artist_meta['id']))
	for _album in albums:
		total += len(_album)
	if total == 0:
		raise Exception('Artist does not have any albums.')
	for _album in albums:
		for num, album in enumerate(_album, 1):
			print('\nAlbum {} of {}:'.format(num, total))
			set(album[0], path=artist_path)

def likes(likes, _):
	total = 0
	folder_name = cfg['media_types']['user_likes']['folder_name']
	likes_path = os.path.join(
		cfg['output_path'], folder_name)
	print('Likes')
	dir_setup(likes_path)
	for like in likes:
		total += len(like)
	if total == 0:
		raise Exception('You do not have any likes.')
	for like in likes:
		for num, _track in enumerate(like, 1):
			print('\nTrack {} of {}:'.format(num, total))
			track(_track['track'], _, path=likes_path, total=total)

def tracks(artist_meta, _):
	total = 0
	template = parse_template(artist_meta, 
		cfg['media_types']['artist_albums']['folder_template'], '{username}')	
	tracks_path = os.path.join(cfg['output_path'], template)
	print(artist_meta['username'] + '\'s tracks')
	dir_setup(tracks_path)
	_tracks = client.get_artist_tracks(str(artist_meta['id']))
	for _track in _tracks:
		total += len(_track)
	if total == 0:
		raise Exception('Artist does not have any tracks.')
	for _track in _tracks:
		for num, _track in enumerate(_track, 1):
			print('\nTrack {} of {}:'.format(num, total))
			track(_track, _, path=tracks_path, num=num, total=total)

def main(url, media_type):
	if media_type in ('albums', 'tracks'):
		meta = client.get_artist_info(url)
	elif media_type == 'likes':
		meta = client.get_user_likes()	
	else:
		meta = client.get_metadata(url)
	globals()[media_type](meta, url)

def cleanup():
	for fname in os.listdir('sc-dl_tmp'):
		os.remove(os.path.join('sc-dl_tmp', fname))

if __name__ == '__main__':
	is_win = platform.system() == 'Windows'
	try:
		if hasattr(sys, 'frozen'):
			os.chdir(os.path.dirname(sys.executable))
		else:
			os.chdir(os.path.dirname(__file__))
	except OSError:
		pass
	print('''
 _____ _____     ____  __    
|   __|     |___|    \|  |   
|__   |   --|___|  |  |  |__ 
|_____|_____|   |____/|_____|
	''')
	cfg = parse_prefs()
	dir_setup('sc-dl_tmp')
	parsed = parse_cookies()
	client = client.Client(parsed)
	plan = client.get_plan()
	is_go_plus = plan == 'Go+'
	print('Signed in successfully - {} account.'.format(plan))
	total = len(cfg['urls'])
	for num, url in enumerate(cfg['urls'], 1):
		print('\nItem {} of {}:'.format(num, total))
		media_type = check_url(url)
		if media_type == None:
			print('Invalid URL:', url)
			continue
		try:
			main(url, media_type)
		except KeyboardInterrupt:
			sys.exit()
		except Exception:
			err('Item failed.')
		finally:
			cleanup()