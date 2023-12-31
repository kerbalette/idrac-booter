import argparse, requests, xmltodict, re, os
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from getpass import getpass
from configparser import ConfigParser
from pathlib import Path

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
    response = requests.post(url, headers=header, proxies=proxies, verify=False )
    if response.status_code == 200:
        return True, response
    else:
        return False, None
             
def authenticate(host, proxies, username, password):
    login_uri = '/data/login'
    header = build_header(host)
    
    url = f'https://{host}{login_uri}'
    data = {'user': username, 'password': password}
    response = requests.post(url, data=data, headers=header, proxies=proxies, verify=False )
    if (response.status_code == 200):
        return True, response
    else:
        return False, None

def extract_tokens(response):
    cookie = response.headers['Set-Cookie']
    dict_data = xmltodict.parse(response.content)
    forwardUrl = dict_data['root']['forwardUrl']
    token_extract = re.search('ST1\=(.*)\,ST2\=(.*)', forwardUrl)
    token1 = token_extract.group(1)
    token2 = token_extract.group(2)
    return cookie, token1, token2


def main():
    parser = argparse.ArgumentParser(description="Integrated Dell Remote Access Controller ('iDrac') Booter")
    parser.add_argument('--host', help='Enter Host name to boot', required=True)
    parser.add_argument('--username', help='Username to authenticate', required=True)
    parser.add_argument('--password', help='Password for authentication', required=True)
    parser.add_argument('--proxyhost', help='Proxy Server',required=False)
    parser.add_argument('--proxyport', help='Proxy Port', required=False, default="8080")
    args = parser.parse_args()

    # Disable SSL errors
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    if (args.proxyhost):
        proxies = {'http':'http://%s:%s' %(args.proxyhost, args.proxyport), 'https':'http://%s:%s' %(args.proxyhost, args.proxyport)}
    else:
        proxies = {}
    
    success, response = authenticate(args.host, proxies, args.username, args.password)
    if success:
        cookie, token1, token2 = extract_tokens(response)
        power_on(args.host, proxies, cookie, token1, token2)
        print(cookie)


if __name__ == "__main__":
    configpath = os.path.expanduser('~') + "/.idrac/config.ini"
    configparser = ConfigParser()
    
    if not os.path.exists(configpath):
        hostname = input('iDrac Host Name: ')
        username = input('Username: ')
        password = getpass()
        proxyhost = input('Proxy host: [Press ENTER for None]: ')
        proxyport = input('Proxy port: [Press ENTER for None]: ')

        configparser.add_section('default')
        configparser.set('default','idrac_host', hostname)
        configparser.set('default','username', username)
        configparser.set('default','password', password)
        configparser.set('default','proxyhost', proxyhost)
        configparser.set('default','proxyport', proxyport)
  
        if not os.path.isdir(configpath):
            posixpath = Path(configpath)
            os.makedirs(posixpath.parent)

        with open(configpath, 'w+') as configfile:
            configparser.write(configfile)

    else:
        configparser.read(configpath)
        hostname = configparser.get('default', 'idrac_host')
        username = configparser.get('default', 'username')
        password = configparser.get('default', 'password')
        proxyhost = configparser.get('default', 'proxyhost')
        proxyport = configparser.get('default', 'proxyport')
    
    if (proxyhost):
        proxies = {'http':'http://%s:%s' %(proxyhost, proxyport), 'https':'http://%s:%s' %(proxyhost, proxyport)}
    else:
        proxies = {}

    # Disable SSL errors
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    success, response = authenticate(hostname, proxies, username, password)
    if success:
        cookie, token1, token2 = extract_tokens(response)
        power_on(hostname, proxies, cookie, token1, token2)
        print(cookie)

   # Refactoring to use configfile main()