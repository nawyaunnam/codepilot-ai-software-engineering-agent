"""Create local secrets without printing them or overwriting an existing environment."""
import getpass
import secrets
from pathlib import Path

path = Path('.env')
if path.exists():
    raise SystemExit('.env already exists; edit it directly to retain existing secrets')
password = getpass.getpass('Choose CodePilot operator password (12+ characters): ')
if len(password) < 12 or any(c in password for c in '\n\r\"\'#$ '):
    raise SystemExit('Use 12+ characters without quotes, whitespace, #, or $')
text = Path('.env.example').read_text()
for key, value in {'ADMIN_PASSWORD': password, 'JWT_SECRET': secrets.token_urlsafe(48),
                   'SANDBOX_TOKEN': secrets.token_urlsafe(48)}.items():
    text = text.replace(f'{key}=\n', f'{key}={value}\n')
with path.open('x') as file:
    path.chmod(0o600)
    file.write(text)
Path('workspace').mkdir(exist_ok=True)
print('Created .env with private permissions. Add LLM_API_KEY there to enable generation.')
