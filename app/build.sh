#!/bin/sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(dirname -- "$app_dir")
dist="$app_dir/dist"
version=$(awk -F '"' '/^version = "/ { print $2; exit }' "$app_dir/Cargo.toml")
platform=$(uname -s)
case "$(uname -m)" in
    arm64|aarch64) ;;
    *)
        printf '%s\n' 'KYW release packages must be built on ARM64.' >&2
        exit 2
        ;;
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
if [ "$platform" = Darwin ]; then
    binary_arch=$(/usr/bin/lipo -archs "$bin")
else
    elf_format=$(od -An -tx1 -N 6 "$bin" | tr -d '[:space:]')
    elf_machine=$(od -An -tx1 -j 18 -N 2 "$bin" | tr -d '[:space:]')
    binary_arch=unknown
    if [ "$elf_format/$elf_machine" = "7f454c460201/b700" ]; then binary_arch=arm64; fi
fi
if [ "$binary_arch" != arm64 ]; then
    printf '%s\n' 'The built executable is not ARM64.' >&2
    exit 1
fi
if [ "${1-}" = --verify ]; then
    "$bin" --self-test
    "$bin" --check
fi
mkdir -p "$dist"
stage=$(mktemp -d "$dist/.build.XXXXXXXX")
trap 'rm -r -- "$stage"' EXIT

case "$platform" in
    Darwin)
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
        ditto -c -k --keepParent "$app" "$stage/kyw-$version-macos-arm64.zip"
        output="$dist/Know Your Wifi.app"
        if [ -d "$output" ]; then mv "$output" "$stage/previous.app"; fi
        if ! mv "$app" "$output"; then
            if [ -d "$stage/previous.app" ]; then mv "$stage/previous.app" "$output"; fi
            exit 1
        fi
        archive="kyw-$version-macos-arm64.zip"
        ;;
    Linux|FreeBSD|OpenBSD)
        case "$platform" in
            Linux) target=linux-arm64 ;;
            FreeBSD) target="freebsd-$(uname -r | cut -d - -f 1)-arm64" ;;
            OpenBSD) target="openbsd-$(uname -r)-arm64" ;;
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
