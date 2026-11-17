#!/bin/bash
set -euo pipefail

app_root=$(cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(dirname -- "$app_root")
dist="$app_root/dist"
output="$dist/Know Your Wifi.app"
mkdir -p "$dist"
stage=$(mktemp -d "$dist/.kyw-build.XXXXXXXX")
previous="$stage/Previous.app"
cleanup() {
    if [[ -e "$previous" && ! -e "$output" ]]; then
        mv "$previous" "$output" || return
    fi
    rm -r -- "$stage"
}
trap cleanup EXIT

swift build --package-path "$app_root" -c release >&2
products=$(swift build --package-path "$app_root" -c release --show-bin-path)
bundle="$stage/Know Your Wifi.app"
contents="$bundle/Contents"
resources="$contents/Resources"
helpers="$contents/Helpers"
mkdir -p "$contents/MacOS" "$helpers" "$resources/Tools" "$resources/Docs" "$resources/Evidence"
cp "$products/KYW" "$contents/MacOS/KYW"
cp "$app_root/Info.plist" "$contents/Info.plist"
cp "$app_root/Resources/"* "$resources/"
cp "$repo_root/docs/"*.md "$resources/Docs/"
cp "$repo_root/evidence/"*.json "$resources/Evidence/"
for name in audit_clm_channels audit_clm_profiles compare_ram_capture inspect_d11_microcode \
    inspect_firmware inspect_hp2p_firmware inspect_radio_sidecars inspect_ranging_result inspect_sleep_wake \
    inventory_board_profiles summarize_switch_timing; do
    cp "$repo_root/tools/$name.py" "$resources/Tools/"
done

target="$(uname -m)-apple-macosx14.0"
xcrun clang -target "$target" -O2 -fobjc-arc -Wall -Wextra -Werror \
    -framework Foundation -framework CoreWLAN -framework IOKit -lIOReport \
    "$repo_root/tools/read_wifi_airtime.m" -o "$helpers/read_wifi_airtime"
xcrun swiftc -target "$target" -swift-version 6 -warnings-as-errors -O \
    "$repo_root/tools/probe_inspection_peer.swift" -o "$helpers/probe_inspection_peer"

plutil -lint "$contents/Info.plist" >&2
codesign --force --sign - "$helpers/read_wifi_airtime" "$helpers/probe_inspection_peer"
codesign --force --sign - "$bundle"
codesign --verify --deep --strict "$bundle"
if [[ -e "$output" ]]; then mv "$output" "$previous"; fi
mv "$bundle" "$output"
printf '%s\n' "$output"
