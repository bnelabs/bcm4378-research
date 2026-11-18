use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use snow::{Builder, TransportState};
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Seek, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};

const CHUNK: usize = 32 * 1024;
const MAX_BYTES: u64 = 2 * 1024 * 1024 * 1024;
const RECEIVE_WINDOW: Duration = Duration::from_secs(600);
const IO_WAIT: Duration = Duration::from_secs(3);
const PROTOCOL: &str = "Noise_NNpsk0_25519_ChaChaPoly_BLAKE2s";

#[derive(Clone)]
pub struct Pairing {
    addresses: Vec<SocketAddrV4>,
    secret: [u8; 32],
}

impl fmt::Display for Pairing {
    fn fmt(&self, out: &mut fmt::Formatter<'_>) -> fmt::Result {
        let addresses = self
            .addresses
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>();
        write!(out, "KYW2 {} ", addresses.join(","))?;
        for byte in self.secret {
            write!(out, "{byte:02x}")?;
        }
        Ok(())
    }
}

impl Pairing {
    pub fn parse(code: &str) -> Option<Self> {
        let mut parts = code.split_whitespace();
        if parts.next()? != "KYW2" {
            return None;
        }
        let addresses = parts
            .next()?
            .split(',')
            .map(str::parse)
            .collect::<Result<Vec<SocketAddrV4>, _>>()
            .ok()?;
        let hex = parts.next()?;
        if addresses.is_empty()
            || addresses.len() > 4
            || !addresses.iter().all(|a| local_ip(*a.ip()) && a.port() != 0)
            || hex.len() != 64
            || !hex.bytes().all(|b| b.is_ascii_hexdigit())
            || parts.next().is_some()
        {
            return None;
        }
        let mut secret = [0; 32];
        for (index, result) in secret.iter_mut().enumerate() {
            *result = u8::from_str_radix(&hex[index * 2..index * 2 + 2], 16).ok()?;
        }
        Some(Self { addresses, secret })
    }

    pub fn path_count(&self) -> usize {
        self.addresses.len()
    }
}

fn local_ip(ip: Ipv4Addr) -> bool {
    ip.is_private() || ip.is_link_local() || ip.is_loopback()
}

pub fn local_addresses() -> Vec<Ipv4Addr> {
    let mut head = std::ptr::null_mut();
    if unsafe { libc::getifaddrs(&mut head) } != 0 {
        return Vec::new();
    }
    let mut results = Vec::new();
    let mut item = head;
    while let Some(record) = unsafe { item.as_ref() } {
        if let Some(addr) = unsafe { record.ifa_addr.as_ref() }
            && i32::from(addr.sa_family) == libc::AF_INET
            && record.ifa_flags & libc::IFF_UP as u32 != 0
        {
            let inet = unsafe { &*record.ifa_addr.cast::<libc::sockaddr_in>() };
            let ip = Ipv4Addr::from(inet.sin_addr.s_addr.to_ne_bytes());
            if local_ip(ip) && !ip.is_loopback() && !results.contains(&ip) {
                results.push(ip);
            }
        }
        item = record.ifa_next;
    }
    unsafe { libc::freeifaddrs(head) };
    results
}

fn invalid() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "Invalid transfer data")
}

fn packet_read(socket: &mut TcpStream) -> io::Result<Vec<u8>> {
    let mut size = [0; 2];
    socket.read_exact(&mut size)?;
    let size = usize::from(u16::from_be_bytes(size));
    if size == 0 || size > CHUNK + 16 {
        return Err(invalid());
    }
    let mut bytes = vec![0; size];
    socket.read_exact(&mut bytes)?;
    Ok(bytes)
}

fn packet_write(socket: &mut TcpStream, data: &[u8]) -> io::Result<()> {
    let size = u16::try_from(data.len()).map_err(|_| invalid())?;
    socket.write_all(&size.to_be_bytes())?;
    socket.write_all(data)
}

struct SecureStream {
    socket: TcpStream,
    cipher: TransportState,
}

impl SecureStream {
    fn open(mut socket: TcpStream, key: &[u8; 32], sending: bool) -> io::Result<Self> {
        socket.set_nonblocking(false)?;
        socket.set_read_timeout(Some(IO_WAIT))?;
        socket.set_write_timeout(Some(IO_WAIT))?;
        socket.set_nodelay(true)?;
        let builder = Builder::new(PROTOCOL.parse().map_err(|_| invalid())?).psk(0, key);
        let mut handshake = if sending {
            builder.build_initiator()
        } else {
            builder.build_responder()
        }
        .map_err(|_| invalid())?;
        let mut buffer = [0; 256];
        for write in [sending, !sending] {
            if write {
                let size = handshake
                    .write_message(&[], &mut buffer)
                    .map_err(|_| invalid())?;
                packet_write(&mut socket, &buffer[..size])?;
            } else {
                handshake
                    .read_message(&packet_read(&mut socket)?, &mut buffer)
                    .map_err(|_| invalid())?;
            }
        }
        Ok(Self {
            socket,
            cipher: handshake.into_transport_mode().map_err(|_| invalid())?,
        })
    }

    fn write(&mut self, plain: &[u8]) -> io::Result<()> {
        if plain.len() > CHUNK {
            return Err(invalid());
        }
        let mut encoded = vec![0; plain.len() + 16];
        let size = self
            .cipher
            .write_message(plain, &mut encoded)
            .map_err(|_| invalid())?;
        packet_write(&mut self.socket, &encoded[..size])
    }

    fn read(&mut self) -> io::Result<Vec<u8>> {
        let packet = packet_read(&mut self.socket)?;
        let mut plain = vec![0; packet.len()];
        let size = self
            .cipher
            .read_message(&packet, &mut plain)
            .map_err(|_| invalid())?;
        plain.truncate(size);
        Ok(plain)
    }
}

#[derive(Clone, Deserialize, Eq, PartialEq, Serialize)]
struct FileInfo {
    name: String,
    bytes: u64,
    sha256: [u8; 32],
}

fn valid_file_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 160
        && !name.starts_with('.')
        && !name.contains(['/', '\\', ':'])
        && !name.chars().any(char::is_control)
}

#[derive(Clone)]
pub enum Progress {
    Sending {
        done: u64,
        total: u64,
        resumed: bool,
    },
    Receiving {
        done: u64,
        total: u64,
    },
    Sent {
        name: String,
        bytes: u64,
        resumed: bool,
        changed_address: bool,
    },
    Saved {
        name: String,
        bytes: u64,
    },
    Error(&'static str),
    Expired,
}

pub struct Receiver {
    pub pairing: Pairing,
    stop: Arc<AtomicBool>,
}

impl Drop for Receiver {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
    }
}

struct Incoming {
    details: FileInfo,
    file: File,
    staged: PathBuf,
    received: u64,
    hash: Sha256,
    completed_name: Option<String>,
}

impl Incoming {
    fn new(details: FileInfo, directory: &Path) -> io::Result<Self> {
        let mut random = [0; 16];
        getrandom::fill(&mut random).map_err(|_| invalid())?;
        let staged = directory.join(format!(".kyw-{:032x}.partial", u128::from_be_bytes(random)));
        let file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .mode(0o600)
            .open(&staged)?;
        Ok(Self {
            details,
            file,
            staged,
            received: 0,
            hash: Sha256::new(),
            completed_name: None,
        })
    }

    fn commit(&mut self, directory: &Path) -> io::Result<String> {
        if let Some(name) = &self.completed_name {
            return Ok(name.clone());
        }
        if <[u8; 32]>::from(self.hash.clone().finalize()) != self.details.sha256 {
            return Err(invalid());
        }
        self.file.sync_all()?;
        for index in 0..100 {
            let name = if index == 0 {
                self.details.name.clone()
            } else {
                format!("{index} - {}", self.details.name)
            };
            match fs::hard_link(&self.staged, directory.join(&name)) {
                Ok(()) => {
                    self.completed_name = Some(name.clone());
                    return Ok(name);
                }
                Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
                Err(error) => return Err(error),
            }
        }
        Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "No unused file name",
        ))
    }
}

impl Drop for Incoming {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.staged);
    }
}

fn receive_attempt(
    listener: TcpStream,
    key: &[u8; 32],
    folder: &Path,
    incoming: &mut Option<Incoming>,
    stop: &AtomicBool,
    emit: &impl Fn(Progress),
) -> io::Result<()> {
    let mut connection = SecureStream::open(listener, key, false)?;
    let details: FileInfo = serde_json::from_slice(&connection.read()?).map_err(|_| invalid())?;
    if details.bytes > MAX_BYTES || !valid_file_name(&details.name) {
        return Err(invalid());
    }
    if incoming.is_none() {
        *incoming = Some(Incoming::new(details.clone(), folder)?);
    }
    let stage = incoming.as_mut().ok_or_else(invalid)?;
    if stage.details != details {
        return Err(invalid());
    }
    connection.write(&stage.received.to_be_bytes())?;
    if stage.received < details.bytes {
        stage.file.set_len(stage.received)?;
        stage.file.seek(io::SeekFrom::Start(stage.received))?;
    }
    let mut last_update = Instant::now() - Duration::from_secs(1);
    while stage.received < details.bytes && !stop.load(Ordering::Relaxed) {
        let data = connection.read()?;
        if data.len() as u64 != (details.bytes - stage.received).min(CHUNK as u64) {
            return Err(invalid());
        }
        stage.file.write_all(&data)?;
        stage.hash.update(&data);
        stage.received += data.len() as u64;
        connection.write(&stage.received.to_be_bytes())?;
        if last_update.elapsed() >= Duration::from_millis(125) {
            emit(Progress::Receiving {
                done: stage.received,
                total: details.bytes,
            });
            last_update = Instant::now();
        }
    }
    if stop.load(Ordering::Relaxed) || connection.read()? != b"finish" {
        return Err(invalid());
    }
    let newly_saved = stage.completed_name.is_none();
    let saved_name = stage.commit(folder)?;
    if newly_saved {
        emit(Progress::Saved {
            name: saved_name,
            bytes: details.bytes,
        });
    }
    connection.write(b"saved")
}

pub fn inbox() -> Option<PathBuf> {
    let home = PathBuf::from(std::env::var_os("HOME")?);
    home.is_absolute().then(|| {
        let downloads = home.join("Downloads");
        if downloads.is_dir() {
            downloads.join("KYW transfers")
        } else {
            home.join("KYW transfers")
        }
    })
}

pub fn start_receiver(
    addresses: &[Ipv4Addr],
    folder: PathBuf,
    emit: impl Fn(Progress) + Send + 'static,
) -> Result<Receiver, &'static str> {
    let listeners = addresses
        .iter()
        .take(4)
        .filter_map(|&address| {
            let listener = TcpListener::bind(SocketAddrV4::new(address, 0)).ok()?;
            listener.set_nonblocking(true).ok()?;
            match listener.local_addr().ok()? {
                std::net::SocketAddr::V4(bound) => Some((listener, bound)),
                _ => None,
            }
        })
        .collect::<Vec<_>>();
    if listeners.is_empty() {
        return Err("Connect to a local network before receiving a file.");
    }
    let mut secret = [0; 32];
    getrandom::fill(&mut secret).map_err(|_| "KYW couldn’t generate a pairing code.")?;
    fs::DirBuilder::new()
        .mode(0o700)
        .recursive(true)
        .create(&folder)
        .map_err(|_| "KYW couldn’t open the folder for received files.")?;
    let stop = Arc::new(AtomicBool::new(false));
    let stopping = stop.clone();
    let pairing = Pairing {
        addresses: listeners.iter().map(|(_, address)| *address).collect(),
        secret,
    };
    thread::spawn(move || {
        let start = Instant::now();
        let mut transfer = None;
        while !stopping.load(Ordering::Relaxed) && start.elapsed() < RECEIVE_WINDOW {
            if let Some(socket) = listeners
                .iter()
                .find_map(|(listener, _)| listener.accept().ok().map(|(socket, _)| socket))
            {
                let _ = receive_attempt(socket, &secret, &folder, &mut transfer, &stopping, &emit);
            } else {
                thread::sleep(Duration::from_millis(20));
            }
        }
        if !stopping.load(Ordering::Relaxed) {
            emit(Progress::Expired);
        }
    });
    Ok(Receiver { pairing, stop })
}

fn read_offset(connection: &mut SecureStream) -> io::Result<u64> {
    connection
        .read()?
        .try_into()
        .map(u64::from_be_bytes)
        .map_err(|_| invalid())
}

struct Sender<'a> {
    file: File,
    info: &'a FileInfo,
    acknowledged: u64,
    resumed: bool,
    interrupt_once: bool,
}

impl Sender<'_> {
    fn send(&mut self, mut connection: SecureStream, emit: &impl Fn(Progress)) -> io::Result<()> {
        let metadata = serde_json::to_vec(self.info).map_err(|_| invalid())?;
        connection.write(&metadata)?;
        let mut offset = read_offset(&mut connection)?;
        if offset > self.info.bytes || (offset != self.info.bytes && offset % CHUNK as u64 != 0) {
            return Err(invalid());
        }
        self.resumed |= offset > 0;
        self.acknowledged = offset;
        self.file.seek(io::SeekFrom::Start(offset))?;
        let mut bytes = [0; CHUNK];
        let mut last_update = Instant::now() - Duration::from_secs(1);
        while offset < self.info.bytes {
            let size = (self.info.bytes - offset).min(CHUNK as u64) as usize;
            self.file.read_exact(&mut bytes[..size])?;
            connection.write(&bytes[..size])?;
            offset += size as u64;
            if read_offset(&mut connection)? != offset {
                return Err(invalid());
            }
            self.acknowledged = offset;
            if last_update.elapsed() >= Duration::from_millis(125) {
                emit(Progress::Sending {
                    done: offset,
                    total: self.info.bytes,
                    resumed: self.resumed,
                });
                last_update = Instant::now();
            }
            if std::mem::take(&mut self.interrupt_once) {
                return Err(io::Error::new(
                    io::ErrorKind::ConnectionAborted,
                    "Test link interruption",
                ));
            }
        }
        connection.write(b"finish")?;
        if connection.read()? != b"saved" {
            return Err(invalid());
        }
        Ok(())
    }
}

pub fn send_file(
    path: &Path,
    pairing: Pairing,
    emit: impl Fn(Progress),
) -> Result<(), &'static str> {
    send_impl(path, pairing, emit, false)
}

fn send_impl(
    path: &Path,
    pairing: Pairing,
    emit: impl Fn(Progress),
    interrupt_once: bool,
) -> Result<(), &'static str> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| valid_file_name(name))
        .ok_or("Choose a file with a regular name.")?
        .to_string();
    let mut file = File::open(path).map_err(|_| "KYW couldn’t read the selected file.")?;
    let metadata = file
        .metadata()
        .map_err(|_| "KYW couldn’t check the selected file.")?;
    if !metadata.is_file() || metadata.len() > MAX_BYTES {
        return Err("Choose an ordinary file up to 2 GiB.");
    }
    let mut hash = Sha256::new();
    let bytes = io::copy(&mut (&mut file).take(metadata.len() + 1), &mut hash)
        .map_err(|_| "KYW couldn’t read the whole file.")?;
    if bytes != metadata.len() {
        return Err("The file changed while KYW was reading it.");
    }
    let info = FileInfo {
        name,
        bytes,
        sha256: hash.finalize().into(),
    };
    let mut sender = Sender {
        file,
        info: &info,
        acknowledged: 0,
        resumed: false,
        interrupt_once,
    };
    let mut since_progress = Instant::now();
    let mut first_progress_address = None;
    for address in pairing.addresses.iter().cycle() {
        let old = sender.acknowledged;
        let sent = TcpStream::connect_timeout(&std::net::SocketAddr::V4(*address), IO_WAIT)
            .and_then(|stream| SecureStream::open(stream, &pairing.secret, true))
            .and_then(|connection| sender.send(connection, &emit));
        if sender.acknowledged > old {
            first_progress_address.get_or_insert(*address);
            since_progress = Instant::now();
        }
        if sent.is_ok() {
            emit(Progress::Sent {
                name: info.name.clone(),
                bytes,
                resumed: sender.resumed,
                changed_address: first_progress_address.is_some_and(|first| first != *address),
            });
            return Ok(());
        }
        if since_progress.elapsed() >= Duration::from_secs(18) {
            break;
        }
        thread::sleep(Duration::from_millis(200));
    }
    Err(
        "The receiver stopped replying. Keep it open and send the same file with the same code to continue.",
    )
}

pub fn self_test() -> Result<(), &'static str> {
    let mut random = [0; 16];
    getrandom::fill(&mut random).map_err(|_| "Couldn’t start the local transfer check.")?;
    let root = std::env::temp_dir().join(format!("kyw-check-{:032x}", u128::from_be_bytes(random)));
    fs::DirBuilder::new()
        .mode(0o700)
        .create(&root)
        .map_err(|_| "Couldn’t start the local transfer check.")?;
    let result = (|| {
        let path = root.join("sample.bin");
        let body = (0..5 * CHUNK)
            .map(|index| (index % 251) as u8)
            .collect::<Vec<_>>();
        fs::write(&path, &body).map_err(|_| "Couldn’t write the local test file.")?;
        let folder = root.join("receive");
        let receiver = start_receiver(
            &[Ipv4Addr::LOCALHOST, Ipv4Addr::LOCALHOST],
            folder.clone(),
            |_| {},
        )?;
        let mut wrong = receiver.pairing.secret;
        wrong[0] ^= 1;
        let first = receiver.pairing.addresses[0];
        let stream =
            TcpStream::connect(first).map_err(|_| "The local test receiver didn’t open.")?;
        if SecureStream::open(stream, &wrong, true).is_ok() {
            return Err("A mismatched pairing code was accepted.");
        }
        let resumed = std::cell::Cell::new(false);
        send_impl(
            &path,
            receiver.pairing.clone(),
            |event| {
                if let Progress::Sent {
                    resumed: true,
                    changed_address: true,
                    ..
                } = event
                {
                    resumed.set(true);
                }
            },
            true,
        )?;
        if !resumed.get()
            || fs::read(folder.join("sample.bin")).ok().as_deref() != Some(body.as_slice())
        {
            return Err("The interrupted file didn’t resume correctly.");
        }
        drop(receiver);
        Ok(())
    })();
    let _ = fs::remove_dir_all(&root);
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn private_address_and_safe_filename_are_required() {
        let code = format!("KYW2 192.0.2.1:4444 {}", "1".repeat(64));
        assert!(Pairing::parse(&code).is_none());
        assert!(!valid_file_name("../file"));
        assert!(!valid_file_name("folder/file"));
        assert!(valid_file_name("Test file.txt"));
    }

    #[test]
    fn encrypted_transfer_survives_a_disconnect() {
        self_test().unwrap();
    }
}
