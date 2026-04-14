import argparse, requests, xmltodict, re, os
import keyring
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from getpass import getpass
from configparser import ConfigParser
from pathlib import Path

KEYRING_SERVICE = "idrac-booter"

def build_header(host):
    header = {'Host':host,
              'User-Agent':'iDrac Booter v0.1',
              'Accept':'*/*',
              'Accept-Language': 'en-US,en;q=0.5',
              'Accept-Encoding': 'gzip, deflate',
              'Content-Type': 'application/x-www-form-urlencoded',
              'Origin': host,
              'Referer': host + '/login.html',
              'Sec-Fetch-Dest': 'empty',
              'Sec-Fetch-Mode': 'cors',
              'Sec-Fetch-Site': 'same-origin',
              'Te': 'trailers',
              'Connection': 'close'}
    return header


def power_on(host, proxies, cookie, token1, token2):
    poweron_uri = '/data?set=pwState:1'
    header = build_header(host)
    header["Cookie"] = f"{cookie}; tokenvalue={token1}"
    header["St2"] = f"{token2}"

    url = f'https://{host}{poweron_uri}'
    response = requests.post(url, headers=header, proxies=proxies, verify=False)
    if response.status_code == 200:
        return True, response
    else:
        return False, None

def authenticate(host, proxies, username, password):
    login_uri = '/data/login'
    header = build_header(host)

    url = f'https://{host}{login_uri}'
    data = {'user': username, 'password': password}
    response = requests.post(url, data=data, headers=header, proxies=proxies, verify=False)
    if response.status_code == 200:
        return True, response
    else:
        return False, None

def extract_tokens(response):
    try:
        cookie = response.headers['Set-Cookie']
        dict_data = xmltodict.parse(response.content)
        forwardUrl = dict_data['root']['forwardUrl']
        token_extract = re.search(r'ST1=(.*),ST2=(.*)', forwardUrl)
        if not token_extract:
            raise ValueError("Could not extract ST1/ST2 tokens from forwardUrl")
        token1 = token_extract.group(1)
        token2 = token_extract.group(2)
        return cookie, token1, token2
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Failed to parse login response: {e}")


def get_config():
    configpath = os.path.expanduser('~') + "/.idrac/config.ini"
    configparser = ConfigParser()

    if not os.path.exists(configpath):
        hostname = input('iDrac Host Name: ')
        username = input('Username: ')
        password = getpass()
        proxyhost = input('Proxy host: [Press ENTER for None]: ')
        proxyport = input('Proxy port: [Press ENTER for None]: ')

        configparser.add_section('default')
        configparser.set('default', 'idrac_host', hostname)
        configparser.set('default', 'username', username)
        configparser.set('default', 'proxyhost', proxyhost)
        configparser.set('default', 'proxyport', proxyport)

        posixpath = Path(configpath)
        os.makedirs(posixpath.parent, exist_ok=True)

        with open(configpath, 'w+') as configfile:
            configparser.write(configfile)

        keyring.set_password(KEYRING_SERVICE, username, password)
    else:
        configparser.read(configpath)
        hostname = configparser.get('default', 'idrac_host')
        username = configparser.get('default', 'username')
        proxyhost = configparser.get('default', 'proxyhost')
        proxyport = configparser.get('default', 'proxyport')
        password = keyring.get_password(KEYRING_SERVICE, username)
        if password is None:
            password = getpass(f"Password for {username} (will be saved to keyring): ")
            keyring.set_password(KEYRING_SERVICE, username, password)

    return hostname, username, password, proxyhost, proxyport


def main():
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    hostname, username, password, proxyhost, proxyport = get_config()

    if proxyhost:
        proxies = {'http': 'http://%s:%s' % (proxyhost, proxyport), 'https': 'http://%s:%s' % (proxyhost, proxyport)}
    else:
        proxies = {}

    success, response = authenticate(hostname, proxies, username, password)
    if not success:
        print("Authentication failed.")
        return

    try:
        cookie, token1, token2 = extract_tokens(response)
    except RuntimeError as e:
        print(f"Error extracting session tokens: {e}")
        return

    success, _ = power_on(hostname, proxies, cookie, token1, token2)
    if success:
        print(f"Power-on command sent successfully to {hostname}.")
    else:
        print(f"Failed to send power-on command to {hostname}.")


if __name__ == "__main__":
    main()
