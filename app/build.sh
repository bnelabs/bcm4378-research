#!/bin/sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(dirname -- "$app_dir")
dist="$app_dir/dist"
version=2.0.0
platform=$(uname -s)
arch=$(uname -m)
case "$arch" in
    amd64) arch=x86_64 ;;
    arm64|aarch64) arch=aarch64 ;;
esac

if [ "$platform" = Darwin ]; then
    export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-14.0}"
fi
export CARGO_TARGET_DIR="$app_dir/target"
cargo_dir=${CARGO_HOME:-"$HOME/.cargo"}
rust_flags=$(printf '%s\037%s' "--remap-path-prefix=$repo_dir=." "--remap-path-prefix=$cargo_dir=/cargo")
export CARGO_ENCODED_RUSTFLAGS="$rust_flags"

if [ "${1-}" = --verify ]; then
    cargo test --quiet --release --locked --manifest-path "$app_dir/Cargo.toml"
elif [ "$#" != 0 ]; then
    printf '%s\n' 'Usage: app/build.sh [--verify]' >&2
    exit 2
fi
cargo build --quiet --release --locked --manifest-path "$app_dir/Cargo.toml"
bin="$CARGO_TARGET_DIR/release/kyw"
if [ "${1-}" = --verify ]; then
    "$bin" --self-test
    "$bin" --check
fi
mkdir -p "$dist"
stage=$(mktemp -d "$dist/.build.XXXXXXXX")
trap 'rm -r -- "$stage"' EXIT

case "$platform" in
    Darwin)
        [ "$arch" != aarch64 ] || arch=arm64
        app="$stage/Know Your Wifi.app"
        mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
        cp "$bin" "$app/Contents/MacOS/kyw"
        cp "$app_dir/Info.plist" "$app/Contents/"
        cp "$app_dir/Resources/AppIcon.icns" "$app/Contents/Resources/"
        cp "$app_dir/Resources/Inter-LICENSE.txt" "$app/Contents/Resources/"
        cp "$app_dir/THIRD-PARTY-LICENSES.txt" "$app/Contents/Resources/"
        plutil -lint "$app/Contents/Info.plist"
        codesign --force --sign - "$app"
        codesign --verify --strict "$app"
        ditto -c -k --keepParent "$app" "$stage/kyw-$version-macos-$arch.zip"
        output="$dist/Know Your Wifi.app"
        if [ -d "$output" ]; then mv "$output" "$stage/previous.app"; fi
        if ! mv "$app" "$output"; then
            if [ -d "$stage/previous.app" ]; then mv "$stage/previous.app" "$output"; fi
            exit 1
        fi
        archive="kyw-$version-macos-$arch.zip"
        ;;
    Linux|FreeBSD|OpenBSD)
        case "$platform:$arch" in
            Linux:x86_64) target=linux-omarchy-x86_64 ;;
            Linux:aarch64) target=linux-asahi-aarch64 ;;
            Linux:*) target="linux-$arch" ;;
            FreeBSD:*) target="freebsd-$(uname -r | cut -d - -f 1)-$arch" ;;
            OpenBSD:*) target="openbsd-$(uname -r)-$arch" ;;
        esac
        folder="kyw-$version-$target"
        mkdir "$stage/$folder"
        cp "$bin" "$stage/$folder/kyw"
        cp "$app_dir/README.md" "$stage/$folder/README.md"
        cp "$app_dir/THIRD-PARTY-LICENSES.txt" "$stage/$folder/"
        cp "$app_dir/Resources/Inter-LICENSE.txt" "$stage/$folder/"
        archive="$folder.tar.gz"
        tar -czf "$stage/$archive" -C "$stage" "$folder"
        ;;
    *)
        printf '%s\n' "This system has no KYW release target: $platform" >&2
        exit 2
        ;;
esac

mv "$stage/$archive" "$dist/$archive"
printf '%s\n' "$dist/$archive"
