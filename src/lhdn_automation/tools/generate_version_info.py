import re
import sys

_SOURCE_FILE = "lhdn_automation.py"
_OUTPUT_FILE = "version_info.txt"
_APP_NAME = "LHDN_Automation"  # keep in sync with build.ps1's PyInstaller --name


def _read_app_version():
    with open(_SOURCE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not find APP_VERSION in {_SOURCE_FILE}")
    return match.group(1)


def _four_part_tuple(version_string):
    """Pads/truncates a dotted version string to the 4 ints Windows file versions require."""
    parts = []
    for part in version_string.split("."):
        with_int = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(with_int) if with_int else 0)
    parts = (parts + [0, 0, 0, 0])[:4]
    return tuple(parts)

def main():
    app_version = _read_app_version()
    version_tuple = _four_part_tuple(app_version)
    dotted = ".".join(str(part) for part in version_tuple)
    content = f'''# UTF-8
# --version-file flag; syntax reference:
# https://pyinstaller.org/en/stable/usage.html#capturing-windows-version-data
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple!r},
    prodvers={version_tuple!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u"040904B0",
          [
            StringStruct(u"CompanyName", u"Andrew Lim"),
            StringStruct(u"FileDescription", u"LHDN eStamp Automation"),
            StringStruct(u"FileVersion", u"{dotted}"),
            StringStruct(u"InternalName", u"{_APP_NAME}"),
            StringStruct(u"LegalCopyright", u"Andrew Lim 2026"),
            StringStruct(u"OriginalFilename", u"{_APP_NAME}.exe"),
            StringStruct(u"ProductName", u"LHDN Automation"),
            StringStruct(u"ProductVersion", u"{dotted}"),
          ],
        )
      ]
    ),
    VarFileInfo([VarStruct(u"Translation", [1033, 1200])]),
  ],
)
'''
    with open(_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{_OUTPUT_FILE} regenerated for version {dotted} (from APP_VERSION = \"{app_version}\")")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Failed to generate {_OUTPUT_FILE}: {error}", file=sys.stderr)
        sys.exit(1)
