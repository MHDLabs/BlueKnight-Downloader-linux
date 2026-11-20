"""Platform and ABI compatibility tests for PyPI wheel selection."""

from __future__ import annotations

import unittest

from packaging.tags import Tag

from blueknight.engines.wheels import select_compatible_wheel


def wheel(filename, *, yanked=False, packagetype="bdist_wheel"):
    return {
        "filename": filename,
        "packagetype": packagetype,
        "yanked": yanked,
        "url": f"https://files.example.invalid/{filename}",
        "digests": {"sha256": "a" * 64},
    }


class CompatibleWheelTests(unittest.TestCase):
    def setUp(self):
        self.linux_tag = Tag("cp312", "cp312", "manylinux_2_17_x86_64")
        self.windows_tag = Tag("cp312", "cp312", "win_amd64")
        self.universal_tag = Tag("py3", "none", "any")

    def test_linux_prefers_a_native_manylinux_wheel(self):
        linux_wheel = wheel("Pillow-11.3.0-cp312-cp312-manylinux_2_17_x86_64.whl")
        universal_wheel = wheel("Pillow-11.3.0-py3-none-any.whl")
        windows_wheel = wheel("Pillow-11.3.0-cp312-cp312-win_amd64.whl")

        selected = select_compatible_wheel(
            [universal_wheel, windows_wheel, linux_wheel],
            [self.linux_tag, self.universal_tag],
        )

        self.assertEqual(selected, linux_wheel)

    def test_windows_selects_the_windows_abi_wheel(self):
        linux_wheel = wheel("Pillow-11.3.0-cp312-cp312-manylinux_2_17_x86_64.whl")
        universal_wheel = wheel("Pillow-11.3.0-py3-none-any.whl")
        windows_wheel = wheel("Pillow-11.3.0-cp312-cp312-win_amd64.whl")

        selected = select_compatible_wheel(
            [linux_wheel, universal_wheel, windows_wheel],
            [self.windows_tag, self.universal_tag],
        )

        self.assertEqual(selected, windows_wheel)

    def test_universal_wheel_is_used_when_no_native_build_matches(self):
        universal_wheel = wheel("img2pdf-0.6.0-py3-none-any.whl")
        windows_wheel = wheel("img2pdf-0.6.0-cp312-cp312-win_amd64.whl")

        selected = select_compatible_wheel(
            [windows_wheel, universal_wheel],
            [self.linux_tag, self.universal_tag],
        )

        self.assertEqual(selected, universal_wheel)

    def test_yanked_source_and_invalid_files_are_ignored(self):
        files = [
            wheel("Pillow-11.3.0-cp312-cp312-manylinux_2_17_x86_64.whl", yanked=True),
            wheel("not-a-valid-wheel.whl"),
            wheel("Pillow-11.3.0.tar.gz", packagetype="sdist"),
        ]

        self.assertIsNone(select_compatible_wheel(files, [self.linux_tag]))

    def test_current_platform_tags_accept_a_universal_wheel(self):
        universal_wheel = wheel("img2pdf-0.6.0-py3-none-any.whl")

        self.assertEqual(select_compatible_wheel([universal_wheel]), universal_wheel)


if __name__ == "__main__":
    unittest.main()
