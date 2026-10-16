"""Create a random review password without printing it or overwriting existing access."""
import os
from pathlib import Path
import secrets
import subprocess

root = Path(__file__).resolve().parents[1] / '.review-access'
root.mkdir(mode=0o700, exist_ok=True)
root.chmod(0o700)
password_file = root / 'credentials.txt'
hash_file = root / 'htpasswd'
if password_file.exists() or hash_file.exists():
    if not (password_file.exists() and hash_file.exists()):
        raise SystemExit('Incomplete access files; inspect .review-access before retrying.')
    print('Preserved existing review access files.')
else:
    password = secrets.token_urlsafe(32)
    hashed = subprocess.run(
        ['openssl', 'passwd', '-6', '-stdin'], input=password + '\n',
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    with os.fdopen(os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        f.write('Username: reviewer\nPassword: ' + password + '\n')
    # The non-root gateway must read the hash. The parent directory stays 0700
    # and only this hash file is bind-mounted into the container.
    with os.fdopen(os.open(hash_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), 'w') as f:
        f.write('reviewer:' + hashed + '\n')
    hash_file.chmod(0o644)
    print('Created review access. Credentials are in .review-access/credentials.txt.')
