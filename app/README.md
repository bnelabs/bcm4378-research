# Know Your Wifi

Send a file to someone on the same local network, even when the internet is down. If the connection drops, keep KYW open on the receiving computer. The sender can continue from the last saved part. When the receiver has more than one reachable address, KYW can try another one.

## Send or receive a file

1. Open **File handoff** on both computers.
2. On the receiving computer, choose **Receive a file**, select **Start receiving**, and copy the pairing code.
3. Share the code with the sender. On the sending computer, choose or drop a file, paste the code, and select **Send file**.
4. Find the delivered file in **KYW transfers** in Downloads or your home folder.

The pairing code lasts ten minutes. Files up to 2 GiB are encrypted in transit. A completed file is checked against the sender’s copy. If automatic retries run out, send the same file with the same code while the receiving window is still open. Leave the receiver open until the sender sees **File delivered**.

## Check or change your connection

- **Connection check** shows signal and link speed where the system reports them. Check how quickly your router replies or pin the signal before moving to another spot.
- **Channel planner** shows channels your system lists. The offline BCM4378 country tables can show which channel blocks two stored plans share.
- **Geek’s Corner** shows the Wi-Fi chip, firmware, and radio operating system when KYW can identify them. On a wired test Mac with the Wi-Fi radio idle, you can request a change to radio power or channel. Linux and BSD use their system or router settings for those changes.

KYW uses the network paths already available between the computers. It can continue a transfer on an alternate reachable address. Direct control of the BCM4378’s two radio slices remains unverified.

## Run the app

Download the package for your operating system from the project’s releases. On macOS, unzip and open **Know Your Wifi.app**. The macOS build is ad hoc signed. On Linux or BSD, extract the archive and run `./kyw` in a graphical session.

| System | Package |
| --- | --- |
| macOS 14 or later | Apple Silicon or Intel zip |
| Omarchy | Linux x86-64 |
| Asahi Linux | Linux AArch64 |
| FreeBSD 15.1 | x86-64 |
| OpenBSD 8.0 | x86-64 |

Linux needs a Wayland or X11 session with OpenGL. Install `iw` and `iproute2` for live Wi-Fi details and `ethtool` for firmware versions. FreeBSD and OpenBSD need an X11 session with OpenGL support. On Linux or BSD, install `zenity` for a file picker, drop a file onto the window if the desktop supports it, or launch `./kyw FILE`.

## Build and check

Build with Rust 1.88 or newer and the platform’s desktop libraries. macOS also requires the Xcode command-line tools.

```sh
./app/build.sh --verify
```

Packages appear in `app/dist/`. The checks include an encrypted loopback transfer that rejects a mismatched code, interrupts the first connection, resumes through a second listener, and compares the delivered file. A loopback run verifies the transfer logic. A second computer on Wi-Fi is needed to measure a real wireless path.
