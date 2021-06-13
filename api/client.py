import re
import os
import sys
import time
try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

import requests


class Client():

	def __init__(self, cookies):
		self.session = requests.Session()
		self.session.headers.update({
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
						  '(KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36',
			'Referer': 'https://soundcloud.com/'
		})
		self.base = 'https://api-v2.soundcloud.com/'
		oauth_token = cookies.get('oauth_token')
		if oauth_token == None:
			raise Exception(
				'Cookies were dumped whilst not logged in. Please redump them.')
		self.session.headers.update({
			'Authorization': 'OAuth ' + oauth_token
		})
		self.app_ver, self.client_id = self.read_client_id()
		self.plan = self._get_plan()
		self.locale = cookies['sclocale']

	def read_client_id(self):
		path = os.path.join('api', 'id')
		with open(path) as f:
			app_ver, app_id = f.readlines()
		return app_ver, app_id

	def make_call(self, epoint, params=None):
		if params != None:
			params['client_id'] = self.client_id
		r = self.session.get(self.base + epoint, params=params)
		r.raise_for_status()
		return r.json()

	def _get_plan(self):
		resp = self.make_call('me')
		self.user_id = str(resp['id'])
		plans = {
			'free': 'free',
			'pro-unlimited': 'Pro Unlimited',
			'consumer-high-tier': 'Go+',
			'consumer-high-dj-tier': 'Go+ DJ'
		}
		plan = plans[resp['consumer_subscription']['product']['id']]
		return plan

	def get_plan(self):
		return self.plan

	def get_metadata(self, url):
		params = {
			'url': url
		}
		resp = self.make_call('resolve', params=params)
		return resp

	def get_artist_id(self, url):
		r = self.session.get(url)
		r.raise_for_status()
		match = re.search(r'content="soundcloud://users:(\d+)">', r.text)
		return match.group(1)

	def get_artist_info(self, url):
		artist_id = self.get_artist_id(url)
		params = {
			'app_version': self.app_ver,
			'app_locale': self.locale	
		}
		resp = self.make_call('users/' + artist_id, params=params)
		return resp

	def get_artist_albums(self, artist_id):
		meta = []
		offset = 0
		params = {
			'offset': offset,
			'limit': 10,
			'app_version': self.app_ver,
			'app_locale': self.locale	
		}
		while True:
			resp = self.make_call('users/' + artist_id + '/albums', params=params)
			if resp['next_href'] != None:
				offset = unquote(resp['next_href'].split('?offset=')[-1].split('&')[0])			
				if '-' in offset:
					params['offset'] = offset
				else:
					params['offset'] += len(resp['collections'])
			# A generator would be better, but then we wouldn't be able to get a total properly.
			meta.append(resp['collection'])
			if resp['next_href'] == None:
				break
			time.sleep(0.2)
		return meta	

	def get_artist_tracks(self, artist_id):
		meta = []
		offset = 0
		params = {
			'offset': offset,
			'limit': 20,
			'app_version': self.app_ver,
			'app_locale': self.locale	
		}
		while True:
			resp = self.make_call('users/' + artist_id + '/tracks', params=params)
			if resp['next_href'] != None:
				offset = unquote(resp['next_href'].split('?offset=')[-1].split('&')[0])			
				if '-' in offset:
					params['offset'] = offset
				else:
					params['offset'] += len(resp['collections'])
			# A generator would be better, but then we wouldn't be able to get a total properly.
			meta.append(resp['collection'])
			if resp['next_href'] == None:
				break
			time.sleep(0.2)
		return meta

	def get_user_likes(self):
		meta = []
		offset = 0
		params = {
			'offset': offset,
			'limit': 24,
			'app_version': self.app_ver,
			'app_locale': self.locale	
		}
		while True:
			resp = self.make_call('users/' + self.user_id + '/track_likes', params=params)
			if resp['next_href'] != None:
				offset = unquote(resp['next_href'].split('?offset=')[-1].split('&')[0])			
				if '-' in offset:
					params['offset'] = offset
				else:
					params['offset'] += len(resp['collections'])
			# A generator would be better, but then we wouldn't be able to get a total properly.
			meta.append(resp['collection'])
			if resp['next_href'] == None:
				break
			time.sleep(0.2)
		return meta

	def get_manifest(self, url):
		r = self.session.get(url)
		r.raise_for_status()
		manifest_url = r.json()['url']
		r = self.session.get(manifest_url)
		r.raise_for_status()
		return r.text

	def get_file(self, track_id):
		url = '{}tracks/{}/download'.format(self.base, track_id)
		r = self.session.get(url, params={
			'client_id': self.client_id, 'app_version': self.app_ver, 'app_locale': self.locale})
		r.raise_for_status()
		file_url = r.json()['redirectUri']
		r = self.session.head(file_url)
		r.raise_for_status()
		fname = r.headers['Content-Disposition'].split('"')[1]
		return fname, '.' + fname.split('.')[-1], file_url