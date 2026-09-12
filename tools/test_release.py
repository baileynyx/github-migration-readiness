"""Test packaging integrity boundaries independently of the 63 product tests."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import build_release
import check_package


class ReleaseTests(unittest.TestCase):
    def test_builder_uses_committed_bytes_and_refuses_existing_output(self):
        # A release must exclude working-tree edits and untracked runtime files.
        # Exercise real Git objects so checkout line-ending settings cannot make
        # this test pass merely because it repeats the builder's in-memory logic.
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            build_release.git(repo, 'init')
            build_release.git(repo, 'config', 'user.name', 'Package test')
            build_release.git(repo, 'config', 'user.email', 'package-test@example.invalid')
            (repo / 'VERSION').write_text('1.0.0\n', encoding='ascii')
            (repo / 'RELEASE_FILES.txt').write_text('VERSION\npayload.txt\n', encoding='ascii')
            (repo / 'payload.txt').write_bytes(b'committed\n')
            build_release.git(repo, 'add', '.')
            build_release.git(repo, '-c', 'commit.gpgsign=false', 'commit', '-m', 'Synthetic package fixture')
            (repo / 'payload.txt').write_bytes(b'uncommitted edit\n')
            (repo / 'runtime.txt').write_bytes(b'untracked runtime data\n')
            result = build_release.build(repo, repo / 'dist')
            with zipfile.ZipFile(repo / 'dist' / result['archive']) as archive:
                self.assertEqual(archive.read('github-migration-readiness-1.0.0/payload.txt'), b'committed\n')
                self.assertFalse(any(name.endswith('runtime.txt') for name in archive.namelist()))
            with self.assertRaises(ValueError):
                build_release.build(repo, repo / 'dist')

    def archive(self, folder, data):
        path = Path(folder) / 'github-migration-readiness-1.0.0.zip'
        path.write_bytes(data)
        path.with_suffix('.zip.sha256').write_text(
            hashlib.sha256(data).hexdigest() + '  ' + path.name + '\n', encoding='ascii')
        return path

    def test_archive_is_repeatable_and_preserves_binary_and_ref_bytes(self):
        files = {'b.refs': b'a\tb\r\n', 'a.bin': b'\x00\xff'}
        _, one = build_release.package_bytes('1.0.0', 'a' * 40, files)
        _, two = build_release.package_bytes('1.0.0', 'a' * 40, dict(reversed(list(files.items()))))
        self.assertEqual(one, two)
        with tempfile.TemporaryDirectory() as folder:
            root, metadata, _ = check_package.unpack(self.archive(folder, one), Path(folder) / 'out')
            self.assertEqual((root / 'b.refs').read_bytes(), files['b.refs'])
            self.assertEqual((root / 'a.bin').read_bytes(), files['a.bin'])
            self.assertEqual(metadata['source_commit'], 'a' * 40)

    def test_builder_rejects_traversal_and_invalid_version(self):
        for path in ('../escape', '/absolute', 'folder\\escape', 'C:escape'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                build_release.package_bytes('1.0.0', 'a' * 40, {path: b'bad'})
        with self.assertRaises(ValueError):
            build_release.package_bytes('../1', 'a' * 40, {'file': b'ok'})

    def test_changed_archive_fails_checksum_before_extraction(self):
        _, data = build_release.package_bytes('1.0.0', 'a' * 40, {'file': b'ok'})
        with tempfile.TemporaryDirectory() as folder:
            path = self.archive(folder, data)
            path.write_bytes(data + b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                check_package.unpack(path, Path(folder) / 'out')
            self.assertFalse((Path(folder) / 'out').exists())

    def test_missing_or_changed_member_fails_even_with_new_archive_checksum(self):
        name, data = build_release.package_bytes('1.0.0', 'a' * 40, {'file': b'ok'})
        for omit in (True, False):
            modified = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(data)) as original, zipfile.ZipFile(modified, 'w') as output:
                for entry in original.infolist():
                    if entry.filename == name + '/file' and omit:
                        continue
                    content = b'changed' if entry.filename == name + '/file' else original.read(entry.filename)
                    output.writestr(entry, content)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    check_package.unpack(self.archive(folder, modified.getvalue()), Path(folder) / 'out')

    def test_symlink_member_is_rejected(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as output:
            entry = zipfile.ZipInfo('github-migration-readiness-1.0.0/link')
            entry.create_system = 3
            entry.external_attr = 0o120777 << 16
            output.writestr(entry, '../outside')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'file type'):
                check_package.unpack(self.archive(folder, data.getvalue()), Path(folder) / 'out')


if __name__ == '__main__':
    unittest.main()
