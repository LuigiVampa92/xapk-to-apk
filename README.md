# XapkToApk

A simple standalone Python script with no extra library dependencies that converts the `.xapk` file into a normal `.apk` file.

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

### Requirements

You do not need any Python dependencies to run the script; however, you **MUST** have some tools installed in your OS, and paths to their executable **MUST** be set to the `$PATH` environment variable. The script relies on that.

These tools are [apktool](https://github.com/iBotPeaches/Apktool), [zipalign](https://developer.android.com/tools/zipalign) and [apksigner](https://developer.android.com/tools/apksigner).

`apktool` can be installed via your OS package manager: `apt`, `brew`, whatever, or pulled directly from GitHub. `zipalign` and `apksigner` are part of the Android SDK build-tools distribution and must be installed via `sdkmanager` in Android Studio or via CLI.

Do not forget to make symlinks of these tools to the system's `$PATH` environment variable, OR add the entire build-tools directory to it.

### Signing the result apk

Since repackaging the splitted app bundle into the universal apk requires changing the original app's manifest file, the original signature will be broken, and the app must be resigned before you can install it on a real device.

The easiest way to do it is to create an `xapktoapk.sign.properties` file with the values of your keystore file (see `xapktoapk.sign.properties.example` for an example).
This file must be placed in the same directory with `xapktoapk.py` script, OR you can put it in your user home directory (`~`).
This way, repacked apk files will be signed automatically. 

By default, the resigning of the result apk files is disabled.
If you do not want to sign it automatically, you can just do it manually after the conversion is completed.
