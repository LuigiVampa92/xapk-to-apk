# XapkToApk

A simple standalone Python script with no extra library dependencies (requires Python 3.8+) that converts the `.xapk` file into a normal `.apk` file.

### Usage

The usage is very simple.

First, clone the repo and make sure the script has execution permission:
```
git clone https://github.com/LuigiVampa92/xapk-to-apk
cd xapk-to-apk
chmod +x xapktoapk.py
```

Get your .xapk file ready, put it near the script, and execute the script: 
```
python xapktoapk.py application.xapk
```

You can put the symlink to this script into the path. Like this (the absolute path to the script depends on your OS and home directory settings):
```
ln -s /home/username/github/xapk-to-apk/xapktoapk.py /usr/local/bin/xapktoapk
``` 
After that, the script can be executed from any directory, like this:
```
xapktoapk application.xapk
```
The result apk file `application.apk` will be placed next to your xapk file, in the same directory.

### Requirements & Installing the missing tools

You do not need any Python dependencies to run the script; however, you **MUST** have some external tools installed, and their executables **MUST** be added to the `$PATH` environment variable. The script relies on that.

Required tools:

| Tool | Purpose | Minimum version |
|---|---|---|
| [Python 3](https://www.python.org/downloads/) | runs the script | 3.8+ |
| [Java runtime](https://adoptium.net/) | required by apktool | 8+ |
| [apktool](https://github.com/iBotPeaches/Apktool) | unpacks and repacks the apk resources | 2.x |
| [zipalign](https://developer.android.com/tools/zipalign) | optimizes the result apk alignment | any build-tools version |
| [apksigner](https://developer.android.com/tools/apksigner) (optional) | signs and verifies the result apk | build-tools 28+ for the v3 signing scheme |

If a tool is missing, the script will tell you right away, e.g.:
```
executable zipalign not found in $PATH, please install it before running xapktoapk
```

#### Installing Python

- **Debian / Ubuntu:** `sudo apt install python3`
- **Fedora:** `sudo dnf install python3`
- **Arch:** `sudo pacman -S python`
- **macOS:** `brew install python` (or use the installer from [python.org](https://www.python.org/downloads/))
- **Windows:** download the installer from [python.org](https://www.python.org/downloads/) and enable the *"Add Python to PATH"* checkbox during the setup

Verify with `python3 --version` (or just `python --version` on Windows).

#### Installing Java

Apktool is a Java application, so a Java runtime (JRE) must be present. Any JDK/JRE 8+ works, e.g. [Eclipse Temurin](https://adoptium.net/):

- **Debian / Ubuntu:** `sudo apt install default-jre-headless`
- **Fedora:** `sudo dnf install java-17-openjdk-headless`
- **Arch:** `sudo pacman -S jre17-openjdk-headless`
- **macOS:** `brew install openjdk`
- **Windows:** download the MSI installer from [adoptium.net](https://adoptium.net/)

Verify with `java -version`.

#### Installing apktool

- **Debian / Ubuntu:** `sudo apt install apktool` (may be an older version; the manual way below is recommended)
- **Fedora:** `sudo dnf install android-apktool`
- **macOS:** `brew install apktool`
- **Windows (with Scoop):** `scoop install apktool`
- **Manual install (any OS, works everywhere):**
  1. Download the [latest apktool wrapper script for your OS](https://github.com/iBotPeaches/Apktool/blob/master/scripts/linux/apktool) and the matching `apktool_*.jar` asset from the [Apktool releases page](https://github.com/iBotPeaches/Apktool/releases) — take the freshest version, e.g. `apktool_2.11.1.jar`
  2. Rename the wrapper to `apktool`, rename the jar to `apktool.jar`, and put **both files** into `/usr/local/bin/` (Linux/macOS) or any directory of your choice (Windows)
  3. Make the wrapper executable: `chmod +x /usr/local/bin/apktool` (Linux/macOS)

Verify with `apktool --version`.

#### Installing zipalign and apksigner

Both binaries ship in the Android SDK **build-tools** package and are installed together with the Android SDK command line tools:

1. Download the [Android SDK command line tools](https://developer.android.com/studio#command-line-tools-only) package (button *"Download Options"* → *"Command line tools only"*, pick your OS)
2. Extract it so that the layout looks like `<sdk-root>/cmdline-tools/latest/bin/`
3. Accept the licenses and install the build tools:
   ```
   sdkmanager --licenses
   sdkmanager "build-tools;36.0.0"
   ```
   You need at least build-tools 28+ for `apksigner`, and 34+ if you want the 16 KB page alignment support (see the signing section below)
4. Add the build-tools directory to `$PATH`

Where the extracted SDK lives depends on how you install it:
- with Android Studio it is typically located in `~/Android/Sdk` (Linux), `$HOME/Library/Android/sdk` (macOS) or `%LOCALAPPDATA%\Android\Sdk` (Windows)

Adding build-tools to `$PATH`:
- **Linux/macOS:** add a line like this to your `~/.bashrc` / `~/.zshrc`:
  ```
  export PATH="$PATH:$HOME/Android/Sdk/build-tools/36.0.0"
  ```
- **Windows:** add e.g. `%LOCALAPPDATA%\Android\Sdk\build-tools\36.0.0` to the `PATH` environment variable via *System Properties → Environment Variables*

Verify with `zipalign` (prints usage on success) and `apksigner --version`.

The easiest way to get everything (java, apktool, zipalign, apksigner) without a manual setup is to use the Docker image — see the Docker section below.

### Signing the result apk

Since repackaging the splitted app bundle into the universal apk requires changing the original app's manifest file, the original signature will be broken, and the app must be resigned before you can install it on a real device.

The easiest way to do it is to create an `xapktoapk.sign.properties` file with the values of your keystore file (see `xapktoapk.sign.properties.example` for an example).
This file must be placed in the same directory with `xapktoapk.py` script, OR you can put it in your user home directory (`~`).
This way, repacked apk files will be signed automatically. 

If you don't want to create a dedicated keystore to sign the result apk files, you can use your default Android SDK debug keystore. In this case, the contents of the `xapktoapk.sign.properties` file should look like this:
```
sign.enabled=true
sign.keystore.file=/home/username/.android/debug.keystore 
sign.keystore.password=android
sign.key.alias=androiddebugkey
sign.key.password=android
```
The `sign.keystore.file` value in the example above is for Linux. Set the absolute path according to your OS and system user name.

By default, the resigning of the result apk files is disabled.
If you do not want to sign it automatically, you don't have to do it. You can just sign the apk file manually after the conversion is completed.

When signing is enabled, the result apk is signed with all three signature schemes enabled by default (`v1`, `v2` and `v3`), and the signature is verified automatically right after signing. All schemes require a keystore whose validity covers current date; `v3` additionally requires apksigner shipped with build-tools 28+. Each scheme can be toggled separately with the following values in the properties file:
```
sign.v1.enabled=true
sign.v2.enabled=true
sign.v3.enabled=true
```

Optionally, you can enable 16 KB zipalign page size for native libraries (recommended/required on Android 15+ devices with 16 KB page size, requires build-tools 34+):
```
zipalign.page.size=16
```

### Docker

Alternatively you can build and use the docker image to have a readily available environment. Ensure you have a folder containing your XAPK to mount to the container. 
```bash
docker build -t xapktoapk .
docker run --rm -it -v ./data:/mnt/data xapktoapk /mnt/data/app.xapk
```
You may optionally mount your own properties file and keystore, in which case the values of `sign.keystore.file` in the mounted properties file should point to `/mnt/debug.keystore`:
```bash
docker build -t xapktoapk .
docker run --rm -it \
	-v ./data:/mnt/data \
	-v ~/.android/debug.keystore:/mnt/debug.keystore:ro \
	-v ./xapktoapk.sign.properties:/xapktoapk/xapktoapk.sign.properties:ro \
	xapktoapk /mnt/data/app.xapk
```
The converted `.apk` file will be available in the `data` folder. 