import os
import sqlite3
import traceback


def get_folder_name(profiles_path):
	paths = []
	for fname in os.listdir(profiles_path):
		path = os.path.join(profiles_path, fname)
		if os.path.isdir(path):
			paths.append(path)
	if len(paths) == 1:
		return paths[0]
	return max(paths, key=os.path.getmtime)

def get_cookies(path):
	parsed = {}
	conn = sqlite3.connect(path)
	cursor = conn.cursor()
	try:
		cursor.execute('SELECT host, name, value FROM moz_cookies')
		for host, name, value in cursor.fetchall():
			if host in ('.soundcloud.com', 'api-auth.soundcloud.com', 'soundcloud.com'):
				parsed[name] = value
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

def main(cookies_path):
	while True:
		parsed = get_cookies(cookies_path)
		if not parsed.get('oauth_token'):
			input(
				'Incomplete cookies or not logged in. Please login if you haven\'t already and refresh your '
				'browser page, then press enter.')
		else:
			break
	write_cookies(parsed)
	print('OK.')

if __name__ == '__main__':
	profiles_path = os.path.join(os.getenv('appdata'), 'Mozilla', 'Firefox', 'profiles')
	folder_name = get_folder_name(profiles_path)
	path = os.path.join(profiles_path, folder_name, 'cookies.sqlite')
	try:
		main(path)
	except Exception:
		traceback.print_exc()
	finally:
		input('Press enter to exit.')