import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image

from django.conf import settings
from django.test import SimpleTestCase


class ApprovedBrandAssetTests(SimpleTestCase):
    header_derivative = 'clm-one-logo-header-tight.svg'
    sidebar_derivatives = {
        'clm-one-logo-reversed-tight.png',
        'clm-one-logo-reversed-tight.svg',
        'clm-one-mark-reversed-tight.png',
        'clm-one-mark-reversed-tight.svg',
    }

    expected_sha256 = {
        'android-chrome-192x192.png': 'eca0529f894b82817cb7448dde7b172a132e84955baa4c6c2cd5b0ff10a5113f',
        'android-chrome-512x512.png': 'da6fa3d123c7758d71ab4e43d2949d4f15620c9f5ed2dee7c9eba4bde47d8ed4',
        'apple-touch-icon.png': '9b3f532fefa1fef512b996ba969ae36f638fe2b34e3df47976b890a0f3f63a9c',
        'clm-one-brand.css': '9387d65d13de6caa77d3ea2372d03dac4fbd12f4212b0e40aae2af43d0caa230',
        'clm-one-logo-exact.svg': '435ec4dc4729d9fa411ef337b01acd904f0cdafdf9f551cae0fa1069b5643be7',
        'clm-one-logo-transparent.png': '8bb2ef4bc6264dabf0d3b75ad4ef7c19ce84cdd74c7914c230a62b3484fd132d',
        'clm-one-logo-transparent.webp': '7189aa4c340bd3a87ef8cb5815aeffa09ea6074daccc4c20228f456723b70fb5',
        'clm-one-mark-exact.svg': '138e8c756d10fec32702135ffc782e5f4f51bb36a0093d9f242bfc1d4240bd69',
        'clm-one-mark-transparent.png': 'ea8672dbe43666ce9b014c3edaff7f6ec1b1164275bd981ff4c15b668ac5f49f',
        'clm-one-mark-transparent.webp': '2e243de6253953b4bd0d3baefe3d1687fa9d5e7ac94fbf42ecee5c90c6f9e5c5',
        'favicon-16x16.png': '194bd7478e2a422f3ae85fc1dc62882789e749cf4a1805c69b1786d972fe530f',
        'favicon-32x32.png': 'c598f972621af6734b55cd45efb670978e96ae19704deb863ebb6445b2dd4a97',
        'favicon.ico': 'f1bd86212fb8dc4eb8f9c8bd8dc44b27115850b55f1b2e50c69aa9886ffa8d80',
        'site.webmanifest': 'f224dbaca8f7a6cd916bcdea5aa9de372890e0dcf2fd09301147a2f5180afa87',
    }

    @property
    def brand_dir(self):
        return Path(settings.BASE_DIR) / 'theme' / 'static' / 'brand'

    def test_canonical_assets_are_exact_approved_files(self):
        actual_names = {path.name for path in self.brand_dir.iterdir() if path.is_file()}
        self.assertEqual(
            actual_names,
            set(self.expected_sha256) | {self.header_derivative} | self.sidebar_derivatives,
        )

        for filename, expected_hash in self.expected_sha256.items():
            digest = hashlib.sha256((self.brand_dir / filename).read_bytes()).hexdigest()
            self.assertEqual(digest, expected_hash, filename)

    def test_header_derivative_only_trims_the_transparent_canvas(self):
        exact_root = ElementTree.parse(self.brand_dir / 'clm-one-logo-exact.svg').getroot()
        tight_root = ElementTree.parse(self.brand_dir / self.header_derivative).getroot()
        namespace = {'svg': 'http://www.w3.org/2000/svg'}

        self.assertEqual(tight_root.attrib['viewBox'], '37 39 1318 269')
        self.assertEqual(tight_root.attrib['width'], '1318')
        self.assertEqual(tight_root.attrib['height'], '269')
        self.assertEqual(
            tight_root.find('svg:image', namespace).attrib['href'],
            exact_root.find('svg:image', namespace).attrib['href'],
        )

    def test_reversed_sidebar_derivatives_preserve_geometry_and_teal(self):
        variants = (
            ('clm-one-logo-transparent.png', 'clm-one-logo-reversed-tight.png'),
            ('clm-one-mark-transparent.png', 'clm-one-mark-reversed-tight.png'),
        )

        for source_name, reversed_name in variants:
            source = Image.open(self.brand_dir / source_name).convert('RGBA')
            source = source.crop(source.getchannel('A').getbbox())
            reversed_image = Image.open(self.brand_dir / reversed_name).convert('RGBA')
            self.assertEqual(reversed_image.size, source.size, reversed_name)

            for original, reversed_pixel in zip(source.getdata(), reversed_image.getdata()):
                red, green, blue, alpha = original
                is_navy = alpha and blue > green * 1.25 and green < 100 and red < 80
                if is_navy:
                    self.assertEqual(reversed_pixel, (255, 255, 255, alpha))
                else:
                    self.assertEqual(reversed_pixel, original)

    def test_shell_uses_tight_full_logo_and_exact_mobile_mark(self):
        shell = (
            Path(settings.BASE_DIR) / 'theme' / 'templates' / 'base.html'
        ).read_text()

        self.assertEqual(shell.count("brand/clm-one-logo-header-tight.svg"), 1)
        self.assertIn("brand/clm-one-logo-reversed-tight.svg", shell)
        self.assertIn("brand/clm-one-mark-reversed-tight.svg", shell)
        self.assertIn('.logo-wordmark    { height: 32px; width: auto;', shell)
        self.assertIn(
            '.sidebar-brand .logo-mark { display: none; height: 32px; width: auto;',
            shell,
        )
        self.assertIn('background: var(--color-shell-deep);', shell)
        self.assertNotIn('padding: 7px 8px;', shell)

    def test_manifest_uses_canonical_static_brand_icons(self):
        manifest = json.loads((self.brand_dir / 'site.webmanifest').read_text())
        self.assertEqual(manifest['name'], 'CLM One')
        self.assertEqual(manifest['short_name'], 'CLM One')
        self.assertEqual(
            [icon['src'] for icon in manifest['icons']],
            [
                '/static/brand/android-chrome-192x192.png',
                '/static/brand/android-chrome-512x512.png',
            ],
        )

    def test_superseded_brand_asset_folder_is_removed(self):
        old_brand_dir = Path(settings.BASE_DIR) / 'theme' / 'static' / 'img' / 'brand'
        self.assertFalse(old_brand_dir.exists())
