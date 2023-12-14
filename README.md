# DRM-Downloader

## What does this script do?
This is a modified version of TPD-Keys that automatically downloads, decrypts, verifies, and merges the mp4 file after grabbing the keys. This version is designed for streams that only use one key for audio and video.

## PATH Requirements
1. [python](https://www.python.org/downloads/release/python-390/)
2. [ffmpeg](https://ffmpeg.org/download.html)
3. [mp4decrypt](https://www.bento4.com/downloads/)
4. [aria2](https://github.com/aria2/aria2)
5. [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Python Requirements
1. requests
2. frida
3. frida-tools
4. protobuf
5. pycryptodome
6. pywidevine
7. httpx

## How to use this program (Google Chrome)
### Preparation
1. Acquire a CDM file.wvd file (see below for guide to obtain CDM using an Android Studio emulator)
2. Install the [Tampermonkey](https://www.tampermonkey.net/) browser extension
3. Install the [EME Logger script](https://greasyfork.org/en/scripts/373903-eme-logger) in Tampermonkey
4. Open the Developer Tools with CTRL+SHIFT+I
5. In the Console tab of the developer window add this to the filter box: MediaKeySession::generateRequest
   - This makes the PSSH pop up in the Console tab when the video loads. 
6. In the Network tab of the developer window add this to the filter box: index.mpd
   - This makes the index.mpd pop up in the Network tab when the video loads. Could also be manifest.mpd
7. (Mode 7 only) In the Network tab of the developer window add this to the filter box: method:POST
   - Find the second ?specConform=true that pops up, click it, and scroll down in the request headers and 
   - find `X-Dt-Custom-Data` and copy the value as your -xdtcd value


### Running the script
1. You can just run the script with no arguments, and you will be prompted for the required inputs.
2. You can also run the script without the input prompt by passing arguments
 `drmdl.py -out "OUTPUT FILE PATH" -pssh "PSSH_HERE" -url "index.mpd URL HERE" -xdtcd "X-Dt-Custom-Data value here"`
### Options for all modes
* -out "path/to/outputfile.mp4"
* -wvd "PATH to WVD file"
* - Optional. Defaults to "./file.wvd"
* -url "URL for index.mpd"
* -pssh "PSSH value"
### Optional options for all modes
* -cc "COUNTRYCODE"
* - Set the two letter country code for the desired proxy country.
### Mode-specific options for each mode
* Use the -selection option to select a mode. The default mode is 7.
#### Mode 1 (Generic without headers)
* -lic "License server url here"
#### Mode 2 (Generic with generic headers)
* -lic "License server url here"
#### Mode 3 (Generic with custom headers from DRMHeaders.py)
* Set your desired custom headers in DRMHeaders.py
#### Mode 4 (JSON Widevine challenge, headers from DRMHeaders.py)
* Set your desired custom headers in DRMHeaders.py
* -lic "License server url here"
* -pid "PID here"
#### Mode 5 (Canal+ Live TV)
* -channel "EpgId here"
* -live_token "Live token here"
#### Mode 6 (YouTube)
* -lic "License server url here"
#### Mode 7 (Generic Header with X-Dt-Custom-Data)
* -xdtcd "Custom X-Dt-Custom-Data value here"
* -lic "License server url here"
    - Optional. Default value can be changed in the script. Defaults to https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true



## Common issues
###### FileNotFoundError on start_process
Make sure you have the dependencies installed and in your PATH

## How to get a CDM file
### Creating a wvd (widevine device file) by extracting keys from an android device.
Here I extract it from android studio emulator using this guide
https://forum.videohelp.com/threads/408031-Dumping-Your-own-L3-CDM-with-Android-Studio/

#### Prerequisites
1. First make sure to check if your PC supports Intel HAXM. If not you may need to use an android phone
2. Enable VT-x and VT-d in BIOS
3. Disable hypervisor on windows

#### Setup the emulator
1. Install android studio
2. Install intel HAXM when android studio asks
3. Create a device 
4. Pixel 6
5. Pie 28 / android 9.0
6. Run the new android device

#### Install python dependencies for everything
```
pip install frida
pip install frida-tools
pip install protobuf
pip install pycryptodome
pip install requests
pip install httpx
pip install pywidevine
```


#### Starting frida server on the emulator
##### Preparation
1. Download frida-server-x.x.x-android-x86.xz https://github.com/frida/frida/releases
2. Make sure it is the same version as the one you installed from pip
3. Extract it (I used peazip) and rename the file to "frida"
4. Move the file you renamed to frida to `C:\Users\yourname\AppData\Local\Android\Sdk\platform-tools`

##### Commands
1. Open CMD and navigate to the same directory
```cd C:\Users\yourname\AppData\Local\Android\Sdk\platform-tools```
2. Check if the android VM is running by running
```adb devices```
3. Now execute these commands to start the frida server on the android device
```
adb push frida /sdcard/
adb shell
su
cp /sdcard/frida /data/local/tmp
chmod +x /data/local/tmp/frida
/data/local/tmp/frida
```

#### Run wvdumper
https://github.com/wvdumper/dumper

```python dump_keys.py```

#### Dump the key files
1. Open Chrome on the android VM and go to any DRM protected video

Your CDM key files will be generated in the key_dumps folder:

`client_id.bin` and `private_key.pem`

The guide recommends renaming them to
`device_client_id_blob` and `device_private_key`


#### Create the device.wvd from the key files:
1. Make a new folder
2. Inside it add the device_client_id_blob and device_private_key files
3. And create a new folder called output
4. Then run this command to create the wvd file in the output folder
```
pywidevine create-device -k device_private_key -c device_client_id_blob -t "ANDROID" -l 3 -o output
```

Rename the file in the output folder to file.wvd and move it to the same folder as drmdl.py
Or rename to whatever you like and add `-wvd "pathtofile.wvd"` to the command

```
python drmdl.py -out "file.mp4" -pssh "" -url "" -xdtcd "" -wvd "pathtofile.wvd"
```


