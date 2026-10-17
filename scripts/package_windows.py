"""Create one portable ZIP and fail before upload if it reaches the size limit."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


MAX_ARCHIVE_BYTES = 2_000_000_000


def package_windows(source, destination, max_bytes=MAX_ARCHIVE_BYTES):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if not source.is_dir():
        raise ValueError(f'Application directory is missing: {source}')
    if destination.is_relative_to(source):
        raise ValueError('The archive must be outside the application directory')
    if not (source / 'VoiceTransl.exe').is_file():
        raise ValueError(f'VoiceTransl.exe is missing from {source}')

    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(source.parent).as_posix())

    size = destination.stat().st_size
    if size >= max_bytes:
        raise ValueError(f'Archive is too large: {size:,} bytes; must be below {max_bytes:,} bytes')
    print(f'Created {destination.name}: {size:,} bytes ({size / 1024**3:.3f} GiB)')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        package_windows(args.source, args.destination)
    except ValueError as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
