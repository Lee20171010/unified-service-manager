#!/usr/bin/env python3
"""Generate a local secret once. Never prints credential values."""
from pathlib import Path
import secrets
import os

root=Path(__file__).resolve().parent.parent
path=root/'.env'
if not path.exists():
    content=(root/'.env.example').read_text().replace('replace-with-a-unique-random-token-at-least-32-characters',secrets.token_urlsafe(48))
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:out.write(content)
    print('Created .env (0600). Administrator token is stored there.')
else:
    print('Existing .env preserved.')
for directory in ['secrets/ssh','data/sources']:(root/directory).mkdir(parents=True,exist_ok=True)
