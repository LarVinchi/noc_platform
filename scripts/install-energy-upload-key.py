#!/usr/bin/env python3
"""Run through the owner's ordinary SSH login to authorize one fixed upload key."""
import base64
import fcntl
import os
from pathlib import Path
import struct
import sys


def restricted_line(public_key, receiver):
    parts = public_key.strip().split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('Expected an Ed25519 public key, without authorized_keys options')
    try:
        blob = base64.b64decode(parts[1], validate=True)
        # Ed25519 SSH wire format: algorithm string followed by a 32-byte key.
        if len(blob) != 51 or blob[:19] != struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Invalid Ed25519 public key') from None
    receiver = str(receiver)
    if not receiver.startswith('/') or any(c in receiver for c in '\r\n"\\'):
        raise ValueError('Invalid receiver path')
    return f'restrict,command="{receiver}" ssh-ed25519 {parts[1]} noc-energy-upload'


def install(home, public_key, receiver):
    line = restricted_line(public_key, receiver)
    folder = home / '.ssh'
    if folder.is_symlink():
        raise ValueError('Refusing a symlinked SSH directory')
    folder.mkdir(mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    path = folder / 'authorized_keys'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        os.fchmod(output.fileno(), 0o600)
        content = output.read(2 * 1024 * 1024 + 1)
        if len(content) > 2 * 1024 * 1024:
            raise ValueError('Unexpectedly large authorized_keys file')
        if line in content.splitlines():
            return 'Upload key is already installed with the required restriction'
        digest = line.split(' ssh-ed25519 ')[1].split()[0]
        if any(digest in existing.split() for existing in content.splitlines() if not existing.lstrip().startswith('#')):
            raise ValueError('This key already exists with different restrictions; use a dedicated upload key')
        output.seek(0, os.SEEK_END)
        output.write(('\n' if content and not content.endswith('\n') else '') + line + '\n')
        output.flush()
        os.fsync(output.fileno())
    return 'Dedicated upload key installed; existing SSH keys preserved'


def main():
    try:
        public_key = sys.stdin.buffer.read(4097)
        if len(public_key) > 4096:
            raise ValueError('Public key is too large')
        receiver = Path(__file__).resolve().with_name('receive-energy-review-workbook.sh')
        if not receiver.is_file() or not os.access(receiver, os.X_OK):
            raise ValueError('The fixed review receiver is missing or is not executable')
        print(install(Path.home(), public_key.decode('ascii'), receiver))
        print('Receiver deployment is separate; this command does not enable company data delivery.')
        return 0
    except (ValueError, OSError) as error:
        print(f'Upload key setup failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
