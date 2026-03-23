import argparse, requests, xmltodict, re, os, sys
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from getpass import getpass
from configparser import ConfigParser
from pathlib import Path

TIMEOUT = 15  # seconds


def build_header(host):
    return {
        'Host': host,
        'User-Agent': 'iDrac Booter v0.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': host,
        'Referer': host + '/login.html',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Te': 'trailers',
        'Connection': 'close',
    }


def authenticate(host, proxies, username, password):
    header = build_header(host)
    url = f'https://{host}/data/login'
    data = {'user': username, 'password': password}
    response = requests.post(url, data=data, headers=header, proxies=proxies, verify=False, timeout=TIMEOUT)
    if response.status_code == 200:
        return response
    return None


def extract_tokens(response):
    cookie = response.headers['Set-Cookie']
    dict_data = xmltodict.parse(response.content)
    forward_url = dict_data['root']['forwardUrl']
    match = re.search(r'ST1=(.*),ST2=(.*)', forward_url)
    if not match:
        raise ValueError(f"Could not extract tokens from forwardUrl: {forward_url}")
    return cookie, match.group(1), match.group(2)


def power_on(host, proxies, cookie, token1, token2):
    header = build_header(host)
    header['Cookie'] = f"{cookie}; tokenvalue={token1}"
    header['St2'] = token2
    url = f'https://{host}/data?set=pwState:1'
    response = requests.post(url, headers=header, proxies=proxies, verify=False, timeout=TIMEOUT)
    return response.status_code == 200


def load_config():
    configpath = os.path.expanduser('~/.idrac/config.ini')
    configparser = ConfigParser()
    if os.path.exists(configpath):
        configparser.read(configpath)
        return {
            'host': configparser.get('default', 'idrac_host', fallback=''),
            'username': configparser.get('default', 'username', fallback=''),
            'password': configparser.get('default', 'password', fallback=''),
            'proxyhost': configparser.get('default', 'proxyhost', fallback=''),
            'proxyport': configparser.get('default', 'proxyport', fallback='8080'),
        }
    return {}


def save_config(host, username, password, proxyhost, proxyport):
    configpath = os.path.expanduser('~/.idrac/config.ini')
    Path(configpath).parent.mkdir(parents=True, exist_ok=True)
    configparser = ConfigParser()
    configparser.add_section('default')
    configparser.set('default', 'idrac_host', host)
    configparser.set('default', 'username', username)
    configparser.set('default', 'password', password)
    configparser.set('default', 'proxyhost', proxyhost)
    configparser.set('default', 'proxyport', proxyport)
    with open(configpath, 'w') as f:
        configparser.write(f)
    print(f"Config saved to {configpath}")


def build_proxies(proxyhost, proxyport):
    if proxyhost:
        proxy_url = f'http://{proxyhost}:{proxyport}'
        return {'http': proxy_url, 'https': proxy_url}
    return {}


def main():
    saved = load_config()

    parser = argparse.ArgumentParser(description="Integrated Dell Remote Access Controller ('iDRAC') Booter")
    parser.add_argument('--host', help='iDRAC hostname', default=saved.get('host') or None, required=not saved.get('host'))
    parser.add_argument('--username', help='Username', default=saved.get('username') or None, required=not saved.get('username'))
    parser.add_argument('--password', help='Password', default=saved.get('password') or None)
    parser.add_argument('--proxyhost', help='Proxy server hostname', default=saved.get('proxyhost', ''))
    parser.add_argument('--proxyport', help='Proxy port', default=saved.get('proxyport', '8080'))
    parser.add_argument('--save', help='Save credentials to ~/.idrac/config.ini', action='store_true')
    args = parser.parse_args()

    password = args.password or getpass(f'Password for {args.username}@{args.host}: ')

    if args.save:
        save_config(args.host, args.username, password, args.proxyhost, args.proxyport)

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    proxies = build_proxies(args.proxyhost, args.proxyport)

    print(f"Authenticating to {args.host}...")
    response = authenticate(args.host, proxies, args.username, password)
    if not response:
        print("Error: Authentication failed.", file=sys.stderr)
        sys.exit(1)

    try:
        cookie, token1, token2 = extract_tokens(response)
    except (KeyError, ValueError) as e:
        print(f"Error: Could not parse authentication response: {e}", file=sys.stderr)
        sys.exit(1)

    print("Sending power-on command...")
    if power_on(args.host, proxies, cookie, token1, token2):
        print(f"Success: Power-on command sent to {args.host}.")
    else:
        print("Error: Power-on command failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
