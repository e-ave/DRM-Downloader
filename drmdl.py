import argparse
import base64
import os
import subprocess
import sys
import tempfile
from base64 import b64encode

from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

import requests
import json
import random
import uuid
import httpx

import DRMHeaders


class Settings:
    def __init__(self, userCountry: str = None, randomProxy: bool = False) -> None:
        self.randomProxy = randomProxy
        self.userCountry = userCountry
        self.ccgi_url = "https://client.hola.org/client_cgi/"
        self.ext_ver = self.get_ext_ver()
        self.ext_browser = "chrome"
        self.user_uuid = uuid.uuid4().hex
        self.user_agent = "Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"
        self.product = "cws"
        self.port_type_choice: str
        self.zoneAvailable = ["AR", "AT", "AU", "BE", "BG", "BR", "CA", "CH", "CL", "CO", "CZ", "DE", "DK", "ES", "FI",
                              "FR", "GR", "HK", "HR", "HU", "ID", "IE", "IL", "IN", "IS", "IT", "JP", "KR", "MX", "NL",
                              "NO", "NZ", "PL", "RO", "RU", "SE", "SG", "SK", "TR", "UK", "US", "GB"]

    def get_ext_ver(self) -> str:
        about = httpx.get("https://hola.org/access/my/settings#/about").text
        if 'window.pub_config.init({"ver":"' in about:
            version = about.split('window.pub_config.init({"ver":"')[1].split('"')[0]
            return version

        # last know working version
        return "1.199.485"


class Engine:
    def __init__(self, Settings) -> None:
        self.settings = Settings

    def get_proxy(self, tunnels, tls=False) -> str:
        login = f"user-uuid-{self.settings.user_uuid}"
        proxies = dict(tunnels)
        protocol = "https" if tls else "http"
        for k, v in proxies["ip_list"].items():
            return "%s://%s:%s@%s:%d" % (
                protocol,
                login,
                proxies["agent_key"],
                k if tls else v,
                proxies["port"][self.settings.port_type_choice],
            )

    def generate_session_key(self, timeout: float = 10.0) -> json:
        post_data = {"login": "1", "ver": self.settings.ext_ver}
        return httpx.post(
            f"{self.settings.ccgi_url}background_init?uuid={self.settings.user_uuid}",
            json=post_data,
            headers={"User-Agent": self.settings.user_agent},
            timeout=timeout,
        ).json()["key"]

    def zgettunnels(
            self, session_key: str, country: str, timeout: float = 10.0
    ) -> json:
        qs = {
            "country": country.lower(),
            "limit": 1,
            "ping_id": random.random(),
            "ext_ver": self.settings.ext_ver,
            "browser": self.settings.ext_browser,
            "uuid": self.settings.user_uuid,
            "session_key": session_key,
        }

        return httpx.post(
            f"{self.settings.ccgi_url}zgettunnels", params=qs, timeout=timeout
        ).json()


class Hola:
    def __init__(self, Settings) -> None:
        self.myipUri: str = "https://hola.org/myip.json"
        self.settings = Settings

    def get_country(self) -> str:

        if not self.settings.randomProxy and not self.settings.userCountry:
            self.settings.userCountry = httpx.get(self.myipUri).json()["country"]

        if (
                not self.settings.userCountry in self.settings.zoneAvailable
                or self.settings.randomProxy
        ):
            self.settings.userCountry = random.choice(self.settings.zoneAvailable)

        return self.settings.userCountry


def init_proxy(data):
    settings = Settings(
        data["zone"]
    )  # True if you want random proxy each request / "DE" for a proxy with region of your choice (German here) / False if you wish to have a proxy localized to your IP address
    settings.port_type_choice = data[
        "port"
    ]  # direct return datacenter ipinfo, peer "residential" (can fail sometime)

    hola = Hola(settings)
    engine = Engine(settings)

    userCountry = hola.get_country()
    session_key = engine.generate_session_key()
    #    time.sleep(10)
    tunnels = engine.zgettunnels(session_key, userCountry)

    return engine.get_proxy(tunnels)


allowed_countries = [
    "AR", "AT", "AU", "BE", "BG", "BR", "CA", "CH", "CL", "CO", "CZ", "DE", "DK", "ES", "FI",
    "FR", "GR", "HK", "HR", "HU", "ID", "IE", "IL", "IN", "IS", "IT", "JP", "KR", "MX", "NL",
    "NO", "NZ", "PL", "RO", "RU", "SE", "SG", "SK", "TR", "UK", "US", "GB"
]

custom_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/octet-stream',
    'DNT': '1',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'X-Dt-Custom-Data': ''
}


def request_decrkey(wvdfile, ipssh, ilicurl, country_code, pid, selection, channel, live_token):
    if selection == 1:
        return request_generic_noheaders(wvdfile, ipssh, ilicurl, country_code)
    elif selection == 2:
        return request_generic_headers(wvdfile, ipssh, ilicurl, country_code)
    elif selection == 3:
        return request_generic_drmheaderspy(wvdfile, ipssh, ilicurl, country_code)
    elif selection == 4:
        return request_widevine_challenge(wvdfile, ipssh, ilicurl, pid, country_code)
    elif selection == 5:
        return request_canalplus(wvdfile, ipssh, country_code, channel, live_token)
    elif selection == 6:
        return request_youtube(wvdfile, ilicurl, country_code)
    elif selection == 7:
        return request_custom(wvdfile, ipssh, ilicurl, country_code)

def request_custom(wvdfile, ipssh, ilicurl, country_code):
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)

    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, data=challenge, headers=custom_headers, proxies=proxies)
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, data=challenge, headers=custom_headers)

    licence.raise_for_status()
    cdm.parse_license(session_id, licence.content)
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys

def request_generic_noheaders(wvdfile, ipssh, ilicurl, country_code):
    print("")
    print("Generic without headers.")
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)
    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, proxies=proxies, data=challenge)
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, data=challenge)
    licence.raise_for_status()
    cdm.parse_license(session_id, licence.content)
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys


def request_generic_headers(wvdfile, ipssh, ilicurl, country_code):
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)

    generic_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, data=challenge, headers=generic_headers, proxies=proxies)
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, data=challenge, headers=generic_headers)
    licence.raise_for_status()
    cdm.parse_license(session_id, licence.content)
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys


def request_widevine_challenge(wvdfile, ipssh, ilicurl, pid, country_code):
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)
    request = b64encode(challenge)
    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, headers=DRMHeaders.headers, proxies=proxies, json={
            "getRawWidevineLicense":
                {
                    'releasePid': pid,
                    'widevineChallenge': str(request, "utf-8")
                }
        })
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, headers=DRMHeaders.headers, json={
            "getRawWidevineLicense":
                {
                    'releasePid': pid,
                    'widevineChallenge': str(request, "utf-8")
                }
        })
    licence.raise_for_status()
    cdm.parse_license(session_id, licence.content)
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys


def request_generic_drmheaderspy(wvdfile, ipssh, ilicurl, country_code):
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)

    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, data=challenge, headers=DRMHeaders.headers, proxies=proxies)
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, data=challenge, headers=DRMHeaders.headers)
    licence.raise_for_status()
    cdm.parse_license(session_id, licence.content)
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys


def request_youtube(wvdfile, ilicurl, country_code):
    ipssh = "AAAAQXBzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAACEiGVlUX01FRElBOjZlMzI4ZWQxYjQ5YmYyMWZI49yVmwY="
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)
    json_data = DRMHeaders.json_data
    json_data["licenseRequest"] = base64.b64encode(challenge).decode("utf-8")
    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, cookies=DRMHeaders.cookies, headers=DRMHeaders.headers, proxies=proxies,
                                json=json_data)
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, cookies=DRMHeaders.cookies, headers=DRMHeaders.headers, json=json_data)

    licence.raise_for_status()
    cdm.parse_license(session_id, licence.json()["license"].replace("-", "+").replace("_", "/"))
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys


def request_canalplus(wvdfile, ipssh, country_code, channel, live_token):
    pssh = PSSH(ipssh)
    device = Device.load(wvdfile)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)
    request = b64encode(challenge)
    ilicurl = "https://secure-browser.canalplus-bo.net/WebPortal/ottlivetv/api/V4/zones/cpfra/devices/31/apps/1/jobs/GetLicence"

    if len(country_code) == 2 and country_code.upper() in allowed_countries:
        proxy = init_proxy({"zone": country_code, "port": "peer"})
        proxies = {
            "http": proxy
        }
        print(f"Using proxy {proxies['http']}")
        licence = requests.post(ilicurl, headers=DRMHeaders.headers, proxies=proxies, json={
            'ServiceRequest': {
                'InData': {
                    'EpgId': channel,
                    'LiveToken': live_token,
                    'UserKeyId': '_sdivii9vz',
                    'DeviceKeyId': '1676391356366-a3a5a7d663de',
                    'ChallengeInfo': f'{request.decode()}',
                    'Mode': 'MKPL',
                },
            },
        })
    else:
        print("Proxy-less request.")
        licence = requests.post(ilicurl, headers=DRMHeaders.headers, json={
            'ServiceRequest': {
                'InData': {
                    'EpgId': channel,
                    'LiveToken': live_token,
                    'UserKeyId': '_jprs988fy',
                    'DeviceKeyId': '1678334845207-61e4e804264c',
                    'ChallengeInfo': f'{request.decode()}',
                    'Mode': 'MKPL',
                },
            },
        })
    licence.raise_for_status()
    cdm.parse_license(session_id, licence.json()["ServiceResponse"]["OutData"]["LicenseInfo"])
    fkeys = ""
    for key in cdm.get_keys(session_id):
        if key.type != 'SIGNING':
            fkeys += key.kid.hex + ":" + key.key.hex() + "\n"
    print("")
    print(fkeys)
    cdm.close(session_id)
    return fkeys


def start_process(command, directory):
    if args.verbose:
        print(directory, " ".join(command))
    process = subprocess.Popen(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()

    if process.returncode != 0:
        print(f"Failure to decrypt: {command[0]} exited with non-zero return code ({process.returncode})")
        stderr = process.stderr.read().decode()
        print(stderr)
        exit(1)
    else:
        print("Process completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-wvd', help='Widevine devide file')
    parser.add_argument('-out', help='OUTPUT FILE PATH; If no absolute path is given it will default to the same '
                                     'directory as the script')
    parser.add_argument('-url', help='VIDEO INDEX.MPD URL')
    parser.add_argument('-lic', help='LICENSE URL')
    parser.add_argument('-pssh', help='PSSH')
    parser.add_argument('-selection', default=7,
                        help='Service Mode Selection (1-7) \n1. Generic without any headers \n2. '
                             'Generic with generic headers \n3. Generic with headers from DRMHeaders.py '
                             '\n4. JSON Widevine challenge, headers from DRMHeaders.py \n5. Canal+ Live '
                             'TV \n6. YouTube VOD \n7. Custom X-Dt-Custom-Data \n', required=False)
    parser.add_argument('-channel', help='Canal+ Channel', required=False)
    parser.add_argument('-live_token', help='Canal+ Live token', required=False)
    parser.add_argument('-cc', help='Country Code for proxy', required=False)
    parser.add_argument('-pid', help='PID for JSON Widevine challenge', required=False)

    parser.add_argument('-xdtcd', help='X-Dt-Custom-Data value for license request headers')
    parser.add_argument('--verbose', "-v", help="increase output verbosity", action="store_true")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        print()

    # Default widevine device file
    if args.wvd is None or args.wvd == "":
        args.wvd = "./file.wvd"

    while args.out is None or args.out == "":
        args.out = input('Enter output file path:')
    while args.url is None or args.url == "":
        args.url = input('Enter index.mpd URL:')
    while args.pssh is None or args.pssh == "":
        args.pssh = input('Enter PSSH:')

    if args.selection == 1 or args.selection == 2 or args.selection == 3:
        while args.lic is None or args.lic == "":
            args.lic = input('Enter license server:')
    elif args.selection == 4:
        while args.lic is None or args.lic == "":
            args.lic = input('Enter license server:')
        while args.pid is None or args.channel == "":
            args.pid = input('Enter PID:')
    elif args.selection == 5:
        while args.channel is None or args.channel == "":
            args.channel = input('Enter Channel:')
        while args.live_token is None or args.live_token == "":
            args.live_token = input('Enter Live Token:')
    elif args.selection == 6:
        while args.lic is None or args.lic == "":
            args.lic = input('Enter license server:')
    elif args.selection == 7:
        if args.lic is None or args.lic == "":
            args.lic = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true"

        while args.xdtcd is None or args.xdtcd == "":
            args.xdtcd = input('Enter X-dt-custom-data:')

    if args.selection != 7:
        args.xdtcd = ""
    custom_headers['X-Dt-Custom-Data'] = args.xdtcd

    args.verbose = True

    if not os.path.isabs(args.out):  # If it's not an absolute path
        args.out = os.path.join(os.getcwd(), args.out)  # Add the current directory to the beginning

    try:
        # Request decryption key using wvd file
        decr_key = request_decrkey(args.wvd, args.pssh, args.lic, args.cc, args.pid, args.selection, args.channel,
                                   args.live_token)

        # Create temp dir
        temp_dir = tempfile.TemporaryDirectory()
        working_dir = temp_dir.name
        if args.verbose:
            print("Creating temporary directory", working_dir)

        if args.verbose:
            print("Downloading Encrypted Audio/Video Files")
        start_process(["yt-dlp", "-o", "file.%(ext)s", "--allow-u", "--external-downloader", "aria2c", "-f", "bv,ba",
                       args.url], working_dir)

        if args.verbose:
            print("Decrypting Audio")
        start_process(["mp4decrypt", "--key", decr_key, "file.m4a", "decrypted_audio.m4a"], working_dir)

        if args.verbose:
            print("Verifying Audio")
        start_process(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of",
                       "default=noprint_wrappers=1:nokey=1", "decrypted_audio.m4a"], working_dir)

        if args.verbose:
            print("Decrypting Video")
        start_process(["mp4decrypt", "--key", decr_key, "file.mp4", "decrypted_video.mp4"], working_dir)

        if args.verbose:
            print("Verifying Video")
        start_process(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of",
                       "default=noprint_wrappers=1:nokey=1", "decrypted_video.mp4"], working_dir)

        if args.verbose:
            print("Combining Decrypted Video & Audio")
        start_process(
            ["ffmpeg", "-y", "-i", "decrypted_video.mp4", "-i", "decrypted_audio.m4a", "-c", "copy", args.out],
            working_dir)

        if args.verbose:
            print("Deleting temporary files")
        temp_dir.cleanup()

        print("Done")

    except Exception as e:
        raise

