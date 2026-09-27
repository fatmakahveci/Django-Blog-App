#!/usr/bin/env python3
"""Prepare and run Folio locally, using only Python's standard library to start."""
import argparse
import importlib.metadata
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent
LOCAL_KEYS = {'DJANGO_SECRET_KEY', 'DJANGO_DEBUG', 'DJANGO_ALLOWED_HOSTS'}
LOOPBACK_HOSTS = {'localhost', '127.0.0.1', '[::1]'}


def local_environment(root, inherited):
    """Read a small, literal environment file without executing shell code."""
    path = root / '.env'
    if not path.exists():
        # Exclusive creation keeps an existing installation's signing key intact.
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(
                    '# Private local settings. Do not commit this file.\n'
                    'DJANGO_DEBUG=true\n'
                    'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]\n'
                    f'DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n'
                )

    values = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, raw_value = line.partition('=')
        key = key.strip()
        if not separator or key not in LOCAL_KEYS or key in values:
            raise ValueError(f'Unsupported or duplicate setting in .env on line {number}.')
        try:
            parts = shlex.split(raw_value, comments=True, posix=True)
        except ValueError:
            raise ValueError(f'Invalid quoting in .env on line {number}.') from None
        if len(parts) > 1:
            raise ValueError(f'Quote values containing spaces in .env on line {number}.')
        values[key] = parts[0] if parts else ''

    # The launch command is explicitly local. WSGI/ASGI and manage.py continue to
    # use deployment environment variables and never implicitly load this file.
    environment = {**values, **inherited}
    if environment.get('DJANGO_DEBUG', '').lower() not in {'true', '1'}:
        raise ValueError('Local startup requires DJANGO_DEBUG=true. Use your deployment server for production.')
    hosts = {host.strip() for host in environment.get('DJANGO_ALLOWED_HOSTS', '').split(',') if host.strip()}
    if '127.0.0.1' not in hosts or not hosts <= LOOPBACK_HOSTS:
        raise ValueError('Local startup requires loopback-only DJANGO_ALLOWED_HOSTS including 127.0.0.1.')
    secret = environment.get('DJANGO_SECRET_KEY', '')
    if len(secret) < 50 or len(set(secret)) < 5 or secret.startswith('django-insecure-'):
        raise ValueError('Set a private, randomly generated DJANGO_SECRET_KEY in .env (at least 50 characters).')
    return environment


def runtime_installed(requirements):
    """Avoid network access on subsequent launches with the pinned runtime present."""
    for line in requirements.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, version = line.strip().split('==', 1)
        try:
            if importlib.metadata.version(name) != version:
                return False
        except importlib.metadata.PackageNotFoundError:
            return False
    return True


def port_number(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('Use a port number between 1024 and 65535.') from None
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError('Use a port number between 1024 and 65535.')
    return port


def prepare_publication(args, interactive):
    import django
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.core.management.base import CommandError

    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    django.setup()
    try:
        call_command('check')
        call_command('migrate', interactive=False)
        if args.demo:
            call_command('seed_demo')

        has_editor = any(
            user.has_usable_password() and user.has_perm('blog_app.add_post')
            for user in get_user_model().objects.filter(is_active=True, is_staff=True)
        )
        if args.create_editor or (not args.setup_only and interactive and not has_editor):
            print('\nCreate your editor account. Choose a username and a private password.\n', flush=True)
            call_command('createsuperuser', interactive=True)
        elif not has_editor:
            print('\nReading is ready. To enable publishing, run in your terminal:\n'
                  '  python3 start.py --create-editor --setup-only\n', flush=True)
    except CommandError as error:
        raise ValueError(str(error)) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Set up and run Folio on your computer.')
    parser.add_argument('--demo', action='store_true', help='Add eight sample articles without overwriting existing content.')
    parser.add_argument('--setup-only', action='store_true', help='Prepare the app without starting a server or prompting for an account.')
    parser.add_argument('--create-editor', action='store_true', help='Prompt for a new editor account, also with --setup-only.')
    parser.add_argument('--port', type=port_number, default=8000, help='Local server port (default: 8000).')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        raise ValueError('Python 3.12 or newer is required. Try python3.14 start.py.')
    if args.create_editor and not sys.stdin.isatty():
        raise ValueError('Create an editor from an interactive terminal so you can choose a private password.')

    environment = local_environment(ROOT, os.environ)
    environment['PYTHONUNBUFFERED'] = '1'
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    virtualenv = ROOT / '.venv'
    python = virtualenv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if Path(sys.prefix).resolve() != virtualenv.resolve():
        if not python.exists():
            print('Creating the local Python environment…', flush=True)
            venv.EnvBuilder(with_pip=True).create(virtualenv)
        result = subprocess.run([str(python), str(ROOT / 'start.py'), *(sys.argv[1:] if argv is None else argv)],
                                cwd=ROOT, env=environment, check=False)
        return result.returncode

    os.chdir(ROOT)
    os.environ.update(environment)
    requirements = ROOT / 'requirements.txt'
    if not runtime_installed(requirements):
        print('Installing the pinned application dependencies…', flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    prepare_publication(args, interactive=sys.stdin.isatty())
    if args.setup_only:
        print('Setup complete. Start Folio with: python3 start.py', flush=True)
        return 0

    print(f'\nFolio:  http://127.0.0.1:{args.port}/\nEditor: http://127.0.0.1:{args.port}/admin/\n'
          'Press Ctrl+C to stop.\n', flush=True)
    # Run Django separately so its autoreloader does not repeat the setup wizard.
    return subprocess.run([sys.executable, str(ROOT / 'manage.py'), 'runserver', f'127.0.0.1:{args.port}'],
                          check=False).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nFolio stopped.')
        raise SystemExit(130)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'\nSetup could not finish: {error}\nFix the issue above and run the same command again.', file=sys.stderr)
        raise SystemExit(1)
