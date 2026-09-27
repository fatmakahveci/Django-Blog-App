from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from start import local_environment, main, prepare_publication


class LocalEnvironmentTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_first_launch_creates_private_key_and_repeated_launch_preserves_it(self):
        first = local_environment(self.root, {})
        original = (self.root / '.env').read_bytes()
        second = local_environment(self.root, {})

        self.assertGreaterEqual(len(first['DJANGO_SECRET_KEY']), 50)
        self.assertEqual(first, second)
        self.assertEqual((self.root / '.env').read_bytes(), original)
        if os.name != 'nt':
            self.assertEqual((self.root / '.env').stat().st_mode & 0o777, 0o600)

    def test_distinct_installations_get_distinct_keys(self):
        other = self.root / 'other'
        other.mkdir()
        self.assertNotEqual(local_environment(self.root, {})['DJANGO_SECRET_KEY'],
                            local_environment(other, {})['DJANGO_SECRET_KEY'])

    def test_shell_environment_takes_precedence(self):
        local_environment(self.root, {})
        secret = secrets.token_urlsafe(64)
        self.assertEqual(local_environment(self.root, {'DJANGO_SECRET_KEY': secret})['DJANGO_SECRET_KEY'], secret)

    def test_deployment_settings_are_rejected_without_overwriting_file(self):
        local_environment(self.root, {})
        original = (self.root / '.env').read_bytes()
        for values in ({'DJANGO_DEBUG': 'false'}, {'DJANGO_ALLOWED_HOSTS': 'example.com'},
                       {'DJANGO_ALLOWED_HOSTS': '*'}, {'DJANGO_ALLOWED_HOSTS': ''},
                       {'DJANGO_SECRET_KEY': 'weak'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                local_environment(self.root, values)
        self.assertEqual((self.root / '.env').read_bytes(), original)

    def test_quotes_exports_comments_and_literal_shell_characters(self):
        marker = self.root / 'must-not-exist'
        secret = f'$(touch {marker})' + secrets.token_urlsafe(64)
        (self.root / '.env').write_text(
            'export DJANGO_DEBUG="true" # local HTTP\n'
            'DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"\n'
            f"DJANGO_SECRET_KEY='{secret}'\n", encoding='utf-8',
        )
        self.assertEqual(local_environment(self.root, {})['DJANGO_SECRET_KEY'], secret)
        self.assertFalse(marker.exists())

    def test_malformed_lines_fail_without_disclosing_values(self):
        for line in ('UNKNOWN=private-value', 'DJANGO_DEBUG="private-value',
                     'DJANGO_SECRET_KEY=private-value with-space',
                     'DJANGO_DEBUG=true\nDJANGO_DEBUG=private-value'):
            with self.subTest(line=line):
                (self.root / '.env').write_text(line, encoding='utf-8')
                with self.assertRaises(ValueError) as result:
                    local_environment(self.root, {})
                self.assertNotIn('private-value', str(result.exception))

    def test_noninteractive_editor_creation_fails_before_setup(self):
        with patch('start.sys.stdin.isatty', return_value=False), patch('start.local_environment') as environment:
            with self.assertRaisesMessage(ValueError, 'interactive terminal'):
                main(['--create-editor', '--setup-only'])
        environment.assert_not_called()


class StartupAccountTests(TestCase):
    def run_setup(self, *, interactive, setup_only=False, create_editor=False):
        args = Namespace(demo=False, setup_only=setup_only, create_editor=create_editor)
        with redirect_stdout(StringIO()) as output, patch('django.core.management.call_command') as command:
            prepare_publication(args, interactive=interactive)
        return [call.args[0] for call in command.call_args_list], output.getvalue()

    def test_first_interactive_launch_prompts_for_an_editor(self):
        commands, _ = self.run_setup(interactive=True)
        self.assertEqual(commands, ['check', 'migrate', 'createsuperuser'])

    def test_setup_only_and_noninteractive_launch_never_prompt(self):
        for interactive, setup_only in ((True, True), (False, False), (False, True)):
            with self.subTest(interactive=interactive, setup_only=setup_only):
                commands, output = self.run_setup(interactive=interactive, setup_only=setup_only)
                self.assertEqual(commands, ['check', 'migrate'])
                self.assertIn('--create-editor --setup-only', output)

    def test_an_unusable_or_unprivileged_account_does_not_skip_onboarding(self):
        get_user_model().objects.create_superuser(username='unusable', password=None)
        get_user_model().objects.create_user(username='staff', password=None, is_staff=True)
        commands, _ = self.run_setup(interactive=True)
        self.assertIn('createsuperuser', commands)

    def test_existing_editor_skips_prompt_unless_explicitly_requested(self):
        # A hashed fixture avoids doing expensive password hashing in setup tests.
        get_user_model().objects.create(username='editor', password='pbkdf2_sha256$fixture',
                                        is_staff=True, is_superuser=True)
        commands, output = self.run_setup(interactive=True)
        self.assertEqual(commands, ['check', 'migrate'])
        self.assertNotIn('--create-editor', output)
        commands, _ = self.run_setup(interactive=True, setup_only=True, create_editor=True)
        self.assertIn('createsuperuser', commands)
