import os
import re
import sys
import json
import traceback

import requests


def write_id(app_ver, client_id):
	path = os.path.join('api', 'id')
	with open(path, 'w') as f:
		f.write(app_ver + '\n' + client_id)
	
def extract_src_urls():
	r = session.get('https://soundcloud.com/discover')
	r.raise_for_status()
	html = r.text
	match = re.search(r'<script>window.__sc_version="(\d{10})"</script>', html)
	matches = re.findall(r'<script crossorigin src="([^"]+)"', html)
	return match.group(1), matches

def extract_client_id(url):
	r = session.get(url)
	r.raise_for_status()
	match = re.search(r'client_id=([a-zA-Z\d]{32})', r.text)
	return match

def main():
	app_ver, urls = extract_src_urls()
	for url in urls:
		match = extract_client_id(url)
		if match == None:
			continue
		write_id(app_ver, match.group(1))
	print('OK.')

if __name__ == '__main__':
	session = requests.Session()
	session.headers.update({
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
					  '(KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36',
		'Referer': 'https://soundcloud.com/'
	})
	try:
		if hasattr(sys, 'frozen'):
			os.chdir(os.path.dirname(sys.executable))
		else:
			os.chdir(os.path.dirname(__file__))
	except OSError:
		pass
	try:
		main()
	except Exception:
		traceback.print_exc()
	finally:
		input('Press enter to exit.')