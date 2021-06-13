import os
import sys
import json
import base64
import sqlite3
import traceback

import win32crypt
from Cryptodome.Cipher import AES


def get_key(local_state_path):
	with open(local_state_path) as f:
		encrypted_key = json.load(f)['os_crypt']['encrypted_key']
	encrypted_key = base64.b64decode(encrypted_key)[5:]
	decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
	return decrypted_key

def handle_decode(x):
	try:
		x = x.decode('UTF-8')
	except UnicodeDecodeError:
		pass
	return x

def get_cookies(cookies_path, key):
	parsed = {}
	conn = sqlite3.connect(cookies_path)
	conn.text_factory = lambda x: handle_decode(x)
	cursor = conn.cursor()
	try:
		cursor.execute('SELECT host_key, name, value, encrypted_value FROM cookies')
		for host, name, value, encrypted_value in cursor.fetchall():
			if not host in ('.soundcloud.com', 'api-auth.soundcloud.com', 'soundcloud.com'):
				continue
			cipher = AES.new(key, AES.MODE_GCM, nonce=encrypted_value[3:3+12])
			decrypted_value = cipher.decrypt_and_verify(encrypted_value[3+12:-16], encrypted_value[-16:])
			parsed[name] = decrypted_value.decode('UTF-8')
	finally:
		conn.close()
	if not parsed:
		raise Exception('Couldn\'t find any SoundCloud cookies.')
	return parsed

def write_cookies(parsed):
	try:
		if hasattr(sys, 'frozen'):
			os.chdir(os.path.dirname(sys.executable))
		else:
			os.chdir(os.path.dirname(__file__))
	except OSError:
		pass
	with open('cookies.txt', 'w', encoding='UTF-8') as f:
		for k, v in parsed.items():
			f.write('{}\t{}\n'.format(k, v))

def main(local_state_path, cookies_path):
	key = get_key(local_state_path)
	while True:
		parsed = get_cookies(cookies_path, key)
		if not parsed.get('oauth_token'):
			input(
				'Incomplete cookies or not logged in. Please login if you haven\'t already and refresh your '
				'browser page, then press enter.')
		else:
			break
	write_cookies(parsed)
	print('OK.')

if __name__ == '__main__':
	user_data_path = os.path.join(os.getenv('localappdata'), 'Google', 'Chrome', 'User Data')
	local_state_path = os.path.join(user_data_path, 'Local State')
	cookies_path = os.path.join(user_data_path, 'Default', 'Cookies')
	try:
		main(local_state_path, cookies_path)
	except Exception:
		traceback.print_exc()
	finally:
		input('Press enter to exit.')