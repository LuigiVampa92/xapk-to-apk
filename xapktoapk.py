#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import os
import platform
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from subprocess import Popen, STDOUT, PIPE


const_dir_tmp = ".xapktoapk"
const_file_target_file = "target"
const_ext_apk = ".apk"
const_ext_xapk = ".xapk"
const_ext_zip = ".zip"

const_file_xapk_manifest = "manifest.json"
const_file_xapk_manifest_key_package_name = "package_name"

const_prefix_apk_split_type_config = "config"
const_suffix_apk_split_type_dpi = "dpi"
const_values_apk_split_type_arch = [ "arm64_v8a", "armeabi_v7a", "armeabi", "x86", "x86_64" ]

const_split_apk_type_main = "main"
const_split_apk_type_arch = "arch"
const_split_apk_type_dpi = "dpi"
const_split_apk_type_locale = "locale"

const_apk_file_apktool_config = 'apktool.yml'
const_apk_dir_lib = 'lib'

const_sign_config_properties_file = 'xapktoapk.sign.properties'

const_zipalign_page_sizes_supported = [ '4', '16' ]

const_signature_schemes_flags = [
    ( 'sign.v1.enabled', '--v1-signing-enabled', 'true' ),
    ( 'sign.v2.enabled', '--v2-signing-enabled', 'true' ),
    ( 'sign.v3.enabled', '--v3-signing-enabled', 'true' ),
]


def print_help():
    print("")
    print("XapkToApk is a tool that converts .xapk file into .apk file")
    print("Can be useful if you want to build a classic fat apk from splitted app bundle")
    print("Usage: python xapktoapk.py PATH_TO_FILE.xapk")
    print("")


def get_param_xapk_file_name():
    return sys.argv[1]


def get_param_xapk_abs_path():
    return os.path.abspath(get_param_xapk_file_name())


def check_sys_args():
    if len(sys.argv) != 2:
        return False
    xapk_file_name = get_param_xapk_file_name()
    if not xapk_file_name.endswith(const_ext_xapk):
        return False
    abspath_to_xapk_file = os.path.abspath(xapk_file_name)
    if not os.path.exists(abspath_to_xapk_file):
        return False
    return True


def is_windows():
    return platform.system() == "Windows"


def get_path_to_batch(batch):
    paths = os.environ['PATH'].split(os.pathsep)
    name = batch + ".bat"
    for path in paths:
        if os.path.isfile(os.path.join(path, name)):
            return os.path.join(path, name)
    return None


def get_executable_in_path(executable):
    path_to_tool = shutil.which(executable)
    if path_to_tool is None and is_windows():
        path_to_tool = get_path_to_batch(executable)
    return path_to_tool


def check_if_executable_exists_in_path(executable):
    return get_executable_in_path(executable) is not None


def execute_tool(command_args_list, working_dir=None):
    # Runs an external tool, captures its combined output and returns (exit_code, output_text).
    # On Windows .bat/.cmd wrappers cannot be executed directly via CreateProcess, run them through cmd.
    executable = command_args_list[0]
    if is_windows() and executable.lower().endswith(('.bat', '.cmd')):
        command_args_list = ['cmd.exe', '/c'] + command_args_list
    process = Popen(command_args_list, stdout=PIPE, stderr=STDOUT, cwd=working_dir)
    raw_output, _ = process.communicate()
    try:
        output = raw_output.decode('utf-8')
    except UnicodeDecodeError:
        output = raw_output.decode('utf-8', errors='replace')
    return process.returncode, output


def error_output_tail(tool_output, max_lines=20):
    lines = tool_output.strip().splitlines()
    if len(lines) <= max_lines:
        return tool_output.strip()
    return '\n'.join(lines[-max_lines:])


def windows_hide_file(file_path):
    execute_tool(["attrib", "+h", file_path])


def create_or_recreate_dir(dir_path):
    if os.path.exists(dir_path):
        if os.path.isdir(dir_path):
            shutil.rmtree(dir_path)
        else:
            os.remove(dir_path)
    os.mkdir(dir_path)
    if is_windows():
        windows_hide_file(dir_path)


def create_tmp_dir(working_dir):
    path_dir_tmp = os.path.abspath(os.path.join(working_dir, const_dir_tmp))
    create_or_recreate_dir(path_dir_tmp)
    return path_dir_tmp


def file_split_name_and_extension(file_path):
    split = os.path.splitext(file_path)
    return split[0], split[1]


def determine_split_type_by_apk_file_name(apk_file_name, xapk_package_name):
    if (xapk_package_name + const_ext_apk) == apk_file_name or 'base.apk' == apk_file_name:
        return const_split_apk_type_main
    if apk_file_name.startswith(const_prefix_apk_split_type_config):
        clear_file_name = os.path.splitext(apk_file_name)[0]
        clear_file_name_splitted = clear_file_name.split('.')
        config_name = clear_file_name_splitted[1] if len(clear_file_name_splitted) > 1 else ''
        if config_name.endswith(const_suffix_apk_split_type_dpi):
            return const_split_apk_type_dpi
        if config_name in const_values_apk_split_type_arch:
            return const_split_apk_type_arch
        return const_split_apk_type_locale
    return const_split_apk_type_locale


def get_apks_of_type(target_apks, type):
    result = list()
    for key in target_apks.keys():
        entry = target_apks[key]
        if entry['apk_split_type'] == type:
            result.append(entry)
    return result


def get_main_apk(target_apks):
    main_apks = get_apks_of_type(target_apks, const_split_apk_type_main)
    if len(main_apks) == 0:
        raise Exception("base apk (main split) not found among the parts of the xapk file")
    return main_apks[0]


def get_do_not_compress_lines(config_file_lines):
    index_start = -1
    index_end = -1
    result = list()
    start_block_literal = 'doNotCompress:'
    prefix_target_line = '- '
    opened = False
    for index, line in enumerate(config_file_lines):
        if not opened and line.startswith(start_block_literal):
            opened = True
            index_start = index + 1
        elif opened and line.startswith(prefix_target_line):
            result.append(line)
        elif opened and not line.startswith(prefix_target_line):
            index_end = index
            break
    if opened and index_end == -1:
        # the block runs to the very end of the file
        index_end = len(config_file_lines)
    result.sort()
    return result, index_start, index_end


def parse_apktool_config(config_file_path):
    config_file_lines = list()
    with open(config_file_path, 'r', encoding='UTF-8') as file:
        config_file_lines = file.readlines()

    do_not_compress_lines, do_not_compress_index_start, do_not_compress_index_end = get_do_not_compress_lines(config_file_lines)

    properties = dict()
    properties['lines_all'] = config_file_lines
    properties['lines_do_not_compress'] = do_not_compress_lines
    properties['lines_do_not_compress_index_start'] = do_not_compress_index_start
    properties['lines_do_not_compress_index_end'] = do_not_compress_index_end

    return properties


def insert_new_lines_do_not_compress(config_file_path, lines_to_insert):
    file_apktool_config = parse_apktool_config(config_file_path)
    do_not_compress_lines_original = file_apktool_config['lines_do_not_compress']

    lines_merged = set()
    lines_merged.update(do_not_compress_lines_original)
    lines_merged.update(lines_to_insert)
    lines_merged = sorted(line if line.endswith('\n') else line + '\n' for line in lines_merged)

    config_file_lines = list(file_apktool_config['lines_all'])
    index_start = file_apktool_config['lines_do_not_compress_index_start']
    index_end = file_apktool_config['lines_do_not_compress_index_end']

    if index_start == -1:
        # no doNotCompress block in this config yet, append a new one to the end of the file
        if len(config_file_lines) > 0 and not config_file_lines[-1].endswith('\n'):
            config_file_lines[-1] += '\n'
        config_file_lines.append('doNotCompress:\n')
        config_file_lines = config_file_lines + lines_merged
    else:
        # replace exactly the block contents, keeping the surrounding lines intact
        config_file_lines[index_start:index_end] = lines_merged

    with open(config_file_path, 'w', encoding='UTF-8') as file:
        file.writelines(config_file_lines)


def merge_apk_arch(dir_apk_main, dir_apk_arch):
    path_libs_src = os.path.join(dir_apk_arch, const_apk_dir_lib)
    path_libs_dst = os.path.join(dir_apk_main, const_apk_dir_lib)
    if not os.path.exists(path_libs_dst):
        os.mkdir(path_libs_dst)

    for dir in os.listdir(path_libs_src):
        src = os.path.join(path_libs_src, dir)
        dst = os.path.join(path_libs_dst, dir)
        shutil.copytree(src, dst, dirs_exist_ok=True)

    path_file_config_src = os.path.join(dir_apk_arch, const_apk_file_apktool_config)
    path_file_config_dst = os.path.join(dir_apk_main, const_apk_file_apktool_config)

    config_src = parse_apktool_config(path_file_config_src)
    insert_new_lines_do_not_compress(path_file_config_dst, config_src['lines_do_not_compress'])


def merge_apk_resources(dir_apk_main, dir_apk_with_resources):
    target_res_dir = os.path.join(dir_apk_main, 'res')
    res_dir = os.path.join(dir_apk_with_resources, 'res')

    skip_rel_path = os.path.join('values', 'public.xml')

    files_to_copy = list()
    for root, dirs, files in os.walk(res_dir):
        for dir in dirs:
            target_res_subdir = os.path.join(target_res_dir, dir)
            if not os.path.exists(target_res_subdir):
                os.mkdir(target_res_subdir)
        for file in files:
            res_file_path_abs = os.path.join(root, file)
            res_file_path_rel = os.path.relpath(res_file_path_abs, res_dir)
            if res_file_path_rel == skip_rel_path:
                continue
            res_file_path_target = os.path.join(target_res_dir, res_file_path_rel)
            files_to_copy.append((res_file_path_abs, res_file_path_rel, res_file_path_target))

    for path_src, path_rel, path_dst in files_to_copy:
        if os.path.exists(path_dst):
            if path_rel.startswith('drawable'):
                continue
            continue

        target_subdir_abspath = os.path.abspath(os.path.dirname(path_dst))
        if not os.path.exists(target_subdir_abspath):
            os.mkdir(target_subdir_abspath)

        shutil.copy(path_src, path_dst)


def merge_apk_assets(dir_apk_main, dir_apk_with_asset_pack):
    target_assets_dir = os.path.join(dir_apk_main, 'assets')
    target_asset_pack_dir = os.path.join(target_assets_dir, 'assetpack')
    assets_dir = os.path.join(dir_apk_with_asset_pack, 'assets')
    asset_pack_dir = os.path.join(assets_dir, 'assetpack')

    if not os.path.exists(asset_pack_dir):
        return
    if not os.path.exists(target_assets_dir):
        os.mkdir(target_assets_dir)
    if not os.path.exists(target_asset_pack_dir):
        os.mkdir(target_asset_pack_dir)

    files_to_copy = list()
    for root, dirs, files in os.walk(asset_pack_dir):
        for dir in dirs:
            target_res_subdir = os.path.join(target_asset_pack_dir, dir)
            if not os.path.exists(target_res_subdir):
                os.mkdir(target_res_subdir)
        for file in files:
            asset_pack_file_path_abs = os.path.join(root, file)
            asset_pack_file_path_rel = os.path.relpath(asset_pack_file_path_abs, asset_pack_dir)
            asset_pack_file_path_target = os.path.join(target_asset_pack_dir, asset_pack_file_path_rel)
            files_to_copy.append((asset_pack_file_path_abs, asset_pack_file_path_rel, asset_pack_file_path_target))

    for path_src, path_rel, path_dst in files_to_copy:
        if os.path.exists(path_dst):
            continue
        target_subdir_abspath = os.path.abspath(os.path.dirname(path_dst))
        if not os.path.exists(target_subdir_abspath):
            os.mkdir(target_subdir_abspath)
        shutil.copy(path_src, path_dst)

    path_file_config_src = os.path.join(dir_apk_with_asset_pack, const_apk_file_apktool_config)
    path_file_config_dst = os.path.join(dir_apk_main, const_apk_file_apktool_config)
    config_src = parse_apktool_config(path_file_config_src)
    insert_new_lines_do_not_compress(path_file_config_dst, config_src['lines_do_not_compress'])


def unpack_apk(path_dir_tmp, apk_file_path, number_current, number_total):
    print('[*] unpacking %d of %d' % (number_current, number_total))
    apktool = get_executable_in_path('apktool')
    if apktool is None:
        raise Exception("apktool executable not found in $PATH")
    rc, output = execute_tool([apktool, 'd', '-s', apk_file_path], working_dir=path_dir_tmp)
    if rc != 0:
        raise Exception("failed to unpack %s (apktool exit code %d):\n%s" % (apk_file_path, rc, error_output_tail(output)))
    os.remove(apk_file_path)


def pack_apk(path_dir_tmp, main_apk_dir):
    print('[*] repack apk')
    apktool = get_executable_in_path('apktool')
    if apktool is None:
        raise Exception("apktool executable not found in $PATH")
    rc, output = execute_tool([apktool, 'b', os.path.basename(main_apk_dir)], working_dir=path_dir_tmp)
    if rc != 0:
        raise Exception("failed to pack apk (apktool exit code %d):\n%s" % (rc, error_output_tail(output)))
    built_apk_file_path = os.path.join(path_dir_tmp, main_apk_dir, 'dist', '%s%s' % (os.path.basename(main_apk_dir), const_ext_apk))
    if not os.path.exists(built_apk_file_path):
        raise Exception("result apk not found")

    build_apk_target_file = os.path.join(path_dir_tmp, '%s%s' % (const_file_target_file, const_ext_apk))
    if os.path.exists(build_apk_target_file):
        os.remove(build_apk_target_file)

    shutil.copy(built_apk_file_path, build_apk_target_file)


def zipalign_apk(path_dir_tmp, page_size_kb):
    print('[*] zipalign apk')

    built_apk_file_path = os.path.join(path_dir_tmp, const_file_target_file + const_ext_apk)
    if not os.path.exists(built_apk_file_path):
        raise Exception("result apk not found")

    prefix_aligned = 'aligned_'
    built_apk_file_aligned_path = os.path.join(path_dir_tmp, prefix_aligned + const_file_target_file + const_ext_apk)
    if os.path.exists(built_apk_file_aligned_path):
        os.remove(built_apk_file_aligned_path)

    command = ['zipalign', '-p', '-f', '4', built_apk_file_path, built_apk_file_aligned_path]
    if page_size_kb == '16':
        # native libs must be page aligned to 16 KB for Android 15+ devices with 16 KB page size
        command = ['zipalign', '-p', '-f', '-P', page_size_kb, '4', built_apk_file_path, built_apk_file_aligned_path]

    rc, output = execute_tool(command)
    if rc != 0:
        raise Exception("failed to zipalign apk (zipalign exit code %d):\n%s" % (rc, error_output_tail(output)))
    if not os.path.exists(built_apk_file_aligned_path):
        raise Exception("failed to zipalign apk")

    os.remove(built_apk_file_path)
    shutil.move(built_apk_file_aligned_path, built_apk_file_path)


def build_sign_command(apksigner, sign_config, build_apk_target_file):
    command = [apksigner, 'sign']
    for property_key, scheme_flag, default_value in const_signature_schemes_flags:
        scheme_value = sign_config.get(property_key, default_value).strip().lower()
        command += [scheme_flag, scheme_value]
    command += [
        '--ks', os.path.expanduser(sign_config['sign.keystore.file']),
        '--ks-pass', 'pass:%s' % sign_config['sign.keystore.password'],
        '--ks-key-alias', sign_config['sign.key.alias'],
        '--key-pass', 'pass:%s' % sign_config['sign.key.password'],
        build_apk_target_file
    ]
    return command


def verify_signature(apksigner, build_apk_target_file, path_dir_tmp):
    rc, output = execute_tool([apksigner, 'verify', '--verbose', build_apk_target_file], working_dir=path_dir_tmp)
    if rc != 0:
        raise Exception("signature verification failed (apksigner exit code %d):\n%s" % (rc, error_output_tail(output)))
    verified_lines = [line.strip() for line in output.splitlines() if line.strip().startswith('Verified')]
    print('[*] signature verified:')
    for verified_line in verified_lines:
        print('    %s' % verified_line)


def sign_apk(path_dir_tmp, sign_config):
    build_apk_target_file = os.path.join(path_dir_tmp, '%s%s' % (const_file_target_file, const_ext_apk))
    if not os.path.exists(build_apk_target_file):
        raise Exception("result apk not found")

    enabled_schemes = ''
    for index, (property_key, scheme_flag, default_value) in enumerate(const_signature_schemes_flags):
        if sign_config.get(property_key, default_value).strip().lower() in ('true', '1', 'yes'):
            enabled_schemes += 'v%d ' % (index + 1)

    print('[*] resign apk, enabled schemes: %s' % enabled_schemes.strip())

    apksigner = get_executable_in_path('apksigner')
    if apksigner is None:
        raise Exception("apksigner executable not found in $PATH")

    command = build_sign_command(apksigner, sign_config, build_apk_target_file)
    rc, output = execute_tool(command, working_dir=path_dir_tmp)
    if rc != 0:
        raise Exception("failed to sign apk file (apksigner exit code %d):\n%s" % (rc, error_output_tail(output)))

    verify_signature(apksigner, build_apk_target_file, path_dir_tmp)


def delete_file_if_exists(path_to_file):
    if os.path.exists(path_to_file):
        os.remove(path_to_file)


def resolve_apktool_dummy_names(dir_apk_main):
    # split apks are decoded standalone, so references to resources defined in the base apk
    # come out as APKTOOL_DUMMY_0x... placeholders; restore real names from the base public.xml
    path_public_xml = os.path.join(dir_apk_main, 'res', 'values', 'public.xml')
    if not os.path.exists(path_public_xml):
        return

    names_by_id = dict()
    for public in ET.parse(path_public_xml).getroot().iter('public'):
        res_id = public.get('id')
        res_name = public.get('name')
        if res_id is not None and res_name is not None:
            names_by_id[int(res_id, 16)] = res_name

    pattern_dummy = re.compile(r'APKTOOL_DUMMY_(0x[0-9a-fA-F]+)')

    def replace_dummy(match):
        return names_by_id.get(int(match.group(1), 16), match.group(0))

    res_dir = os.path.join(dir_apk_main, 'res')
    for root, dirs, files in os.walk(res_dir):
        for file in files:
            res_file_path = os.path.join(root, file)
            if not file.endswith('.xml') or res_file_path == path_public_xml:
                continue
            with open(res_file_path, 'r', encoding='UTF-8') as res_file:
                data = res_file.read()
            if 'APKTOOL_DUMMY_' not in data:
                continue
            with open(res_file_path, 'w', encoding='UTF-8') as res_file:
                res_file.write(pattern_dummy.sub(replace_dummy, data))


def delete_signature_related_files(path_to_main_apk):
    # split bundles keep the bundle signing files in original/META-INF,
    # they must not leak into the repacked apk
    meta_inf_dir = os.path.join(path_to_main_apk, 'original', 'META-INF')
    if not os.path.isdir(meta_inf_dir):
        return
    for file in os.listdir(meta_inf_dir):
        if file == 'MANIFEST.MF' or file.startswith('BNDLTOOL.') or file.endswith(('.RSA', '.DSA', '.EC', '.SF')):
            delete_file_if_exists(os.path.join(meta_inf_dir, file))


def update_main_manifest_file(path_main_apk):
    path_manifest = os.path.join(path_main_apk, 'AndroidManifest.xml')
    data = None

    replacements = {
        '<meta-data android:name="com.google.firebase.messaging.default_notification_icon" android:resource="@null"/>': '',
        'android:isSplitRequired="true" ': '',
        'android:requiredSplitTypes="base__abi,base__density" ': '',
        'android:splitTypes="" ': '',
        'android:value="STAMP_TYPE_DISTRIBUTION_APK"': 'android:value="STAMP_TYPE_STANDALONE_APK"',
        '<meta-data android:name="com.android.vending.splits.required" android:value="true"/>': '',
        '<meta-data android:name="com.android.vending.splits" android:resource="@xml/splits0"/>': ''
    }

    with open(path_manifest, 'r', encoding='UTF-8') as file:
        data = file.read()

    for from_str, to_str in replacements.items():
        data = data.replace(from_str, to_str)

    with open(path_manifest, 'w', encoding='UTF-8') as file:
        file.write(data)


def load_sign_properties():
    path_sign_config_file = os.path.abspath(os.path.join(os.getcwd(), const_sign_config_properties_file))
    if not os.path.exists(path_sign_config_file):
        path_sign_config_file = os.path.abspath(os.path.join(os.path.expanduser('~'), const_sign_config_properties_file))
        if not os.path.exists(path_sign_config_file):
            return None

    sign_config_file_lines = list()
    with open(path_sign_config_file, 'r', encoding='UTF-8') as sign_config_file:
        sign_config_file_lines = sign_config_file.readlines()

    properties = dict()
    for line in sign_config_file_lines:
        checked_line = line.strip().replace('\r', '')
        if checked_line == '' or checked_line.startswith('#'):
            continue
        line_parts = checked_line.split('=', 1)
        if len(line_parts) != 2:
            print('[!] ignoring malformed line in the signing config: %s' % checked_line)
            continue
        property_key = line_parts[0].strip()
        property_value = line_parts[1].strip()
        properties[property_key] = property_value

    if not 'sign.enabled' in properties.keys() or properties['sign.enabled'].lower() != 'true':
        return None
    if 'sign.keystore.file' not in properties.keys() or 'sign.keystore.password' not in properties.keys() or 'sign.key.alias' not in properties.keys() or 'sign.key.password' not in properties.keys():
        return None
    keystore_file = os.path.expanduser(properties['sign.keystore.file'])
    if keystore_file == '' or not os.path.exists(keystore_file) or os.path.isdir(keystore_file):
        return None
    if properties['sign.keystore.password'] == '' or properties['sign.key.alias'] == '' or properties['sign.key.password'] == '':
        return None

    page_size = properties.get('zipalign.page.size', '4').strip()
    if page_size not in const_zipalign_page_sizes_supported:
        raise Exception("unsupported zipalign.page.size value '%s', supported values are: %s" % (page_size, ', '.join(const_zipalign_page_sizes_supported)))
    return properties


def build_single_apk(path_to_tmp_dir, path_to_main_apk_dir, should_sign_apk, sign_config):
    pack_apk(path_to_tmp_dir, path_to_main_apk_dir)
    zipalign_apk(path_to_tmp_dir, sign_config.get('zipalign.page.size', '4') if sign_config is not None else '4')
    if should_sign_apk:
        sign_apk(path_to_tmp_dir, sign_config)
    else:
        print('[*] skip signing apk')


def copy_single_apk_to_working_dir(path_to_tmp_dir, path_to_working_dir, target_name):
    file_src = os.path.join(path_to_tmp_dir, const_file_target_file + const_ext_apk)
    if not os.path.exists(file_src) or os.path.isdir(file_src):
        raise Exception("result apk file not found")

    file_dst = os.path.join(path_to_working_dir, target_name + const_ext_apk)
    if os.path.exists(file_dst):
        if os.path.isdir(file_dst):
            shutil.rmtree(file_dst)
        else:
            os.remove(file_dst)

    shutil.copy(file_src, file_dst)


def prioritize_dpi_apk_list_rev_sort(apks_dpi):
    apks_dpi_prioritzed = sorted(apks_dpi, key=lambda x: x['apk_file_name'], reverse=True)
    return apks_dpi_prioritzed


def prioritize_dpi_apk_list(apks_dpi):
    preferrable_order = [ 'config.xxxhdpi', 'config.xxhdpi', 'config.xhdpi', 'config.hdpi', 'config.mdpi', 'config.ldpi', 'config.nodpi', 'config.tvdpi' ]

    apks_dpi_map = dict()
    for apk in apks_dpi:
        apks_dpi_map[apk['apk_dir_name']] = apk

    apks_dpi_prioritzed = list()
    for item in preferrable_order:
        if item in apks_dpi_map.keys():
            apks_dpi_prioritzed.append(apks_dpi_map[item])
            del apks_dpi_map[item]
    if len(apks_dpi_map.keys()) > 0:
        rev_sorted = prioritize_dpi_apk_list_rev_sort(apks_dpi_map.values())
        for apk in rev_sorted:
            apks_dpi_prioritzed.append(apk)

    return apks_dpi_prioritzed


def main():
    if not check_sys_args():
        print_help()
        exit(-1)

    for tested_binary in [ 'apktool', 'zipalign' ]:
        if not check_if_executable_exists_in_path(tested_binary):
            print("executable %s not found in $PATH, please install it before running xapktoapk" % tested_binary)
            exit(-2)

    sign_properties = load_sign_properties()
    should_sign_apk = sign_properties is not None
    if should_sign_apk and not check_if_executable_exists_in_path('apksigner'):
        print("executable apksigner not found in $PATH, please install it before running xapktoapk")
        exit(-2)

    xapk_file_name = get_param_xapk_file_name()
    xapk_file_abs_path = get_param_xapk_abs_path()
    original_file_name, original_file_extension = file_split_name_and_extension(xapk_file_name)

    print('[*] start')
    cwd = os.path.abspath(os.path.curdir)
    path_dir_tmp = create_tmp_dir(cwd)

    try:
        path_target_file_xapk = os.path.join(path_dir_tmp, const_file_target_file + const_ext_xapk)
        shutil.copy(xapk_file_abs_path, path_target_file_xapk)

        target_file_name_zip = const_file_target_file + const_ext_zip
        path_target_file_zip = os.path.join(path_dir_tmp, target_file_name_zip)
        os.rename(path_target_file_xapk, path_target_file_zip)

        print('[*] unpacking xapk')
        with ZipFile(path_target_file_zip, 'r') as zip_file:
            zip_file.extractall(path=path_dir_tmp)
        os.remove(path_target_file_zip)

        xapk_manifest_data = None
        path_xapk_manifest = os.path.join(path_dir_tmp, const_file_xapk_manifest)
        with open(path_xapk_manifest, 'r') as file:
            xapk_manifest_data = json.load(file)
        xapk_package_name = xapk_manifest_data[const_file_xapk_manifest_key_package_name]

        target_apk_file_names = list()
        for file in os.listdir(path_dir_tmp):
            if file.endswith(const_ext_apk):
                file_abspath = os.path.abspath(os.path.join(path_dir_tmp, file))
                if not os.path.isdir(file_abspath):
                    target_apk_file_names.append(file)

        target_apks = dict()
        for apk_file_name in target_apk_file_names:
            apk_type = determine_split_type_by_apk_file_name(apk_file_name, xapk_package_name)
            properties = dict()
            properties['apk_file_name'] = apk_file_name
            properties['apk_file_path'] = os.path.abspath(os.path.join(path_dir_tmp, properties['apk_file_name']))
            properties['apk_dir_name'] = os.path.splitext(apk_file_name)[0]
            properties['apk_dir_path'] = os.path.abspath(os.path.join(path_dir_tmp, properties['apk_dir_name']))
            properties['apk_split_type'] = apk_type
            target_apks[apk_file_name] = properties

        print('[*] xapk file unpacked. %d parts discovered' % len(target_apk_file_names))

        unpack_number_total = len(target_apks.keys())
        for index, apk_file_key in enumerate(target_apks.keys()):
            apk_entry = target_apks[apk_file_key]
            unpack_apk(path_dir_tmp, apk_entry['apk_file_path'], index + 1, unpack_number_total)

        apk_main = get_main_apk(target_apks)
        apks_arch = get_apks_of_type(target_apks, const_split_apk_type_arch)
        apks_dpi = get_apks_of_type(target_apks, const_split_apk_type_dpi)
        apks_locale = get_apks_of_type(target_apks, const_split_apk_type_locale)

        for apk_arch in apks_arch:
            merge_apk_arch(apk_main['apk_dir_path'], apk_arch['apk_dir_path'])
        apks_dpi_prioritzed = prioritize_dpi_apk_list(apks_dpi)
        for apk_dpi in apks_dpi_prioritzed:
            merge_apk_resources(apk_main['apk_dir_path'], apk_dpi['apk_dir_path'])
        for apk_locale in apks_locale:
            merge_apk_resources(apk_main['apk_dir_path'], apk_locale['apk_dir_path'])
            merge_apk_assets(apk_main['apk_dir_path'], apk_locale['apk_dir_path'])

        resolve_apktool_dummy_names(apk_main['apk_dir_path'])
        delete_signature_related_files(apk_main['apk_dir_path'])
        update_main_manifest_file(apk_main['apk_dir_path'])

        build_single_apk(path_dir_tmp, apk_main['apk_dir_path'], should_sign_apk, sign_properties)
        copy_single_apk_to_working_dir(path_dir_tmp, cwd, original_file_name)
    finally:
        # make sure the working directory is restored and the temp dir is cleaned up even on failure
        os.chdir(cwd)
        shutil.rmtree(path_dir_tmp, ignore_errors=True)

    print('[*] complete')


if __name__ == '__main__':
    main()
