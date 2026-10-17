"""Check backend DLL dependencies without requiring a GPU on the build runner."""

import argparse
import os
from pathlib import Path

import pefile


def verify_native_runtime(executable, shared_dir):
    executable = Path(executable).resolve()
    system_dir = Path(os.environ['SystemRoot']) / 'System32'
    search_dirs = (executable.parent, Path(shared_dir).resolve(), system_dir)
    available = {}
    for directory in reversed(search_dirs):
        available.update({path.name.lower(): path for path in directory.iterdir() if path.is_file()})

    pending = [executable, *executable.parent.glob('*.dll')]
    checked = set()
    while pending:
        path = pending.pop()
        if path in checked:
            continue
        checked.add(path)
        with pefile.PE(str(path), fast_load=True) as binary:
            binary.parse_data_directories(directories=[
                pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
                pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT'],
            ])
            imports = list(getattr(binary, 'DIRECTORY_ENTRY_IMPORT', []))
            imports += list(getattr(binary, 'DIRECTORY_ENTRY_DELAY_IMPORT', []))
            for dependency in imports:
                name = dependency.dll.decode('ascii').lower()
                # GPU driver/loader DLLs come from the user's graphics driver,
                # and can be absent from CPU-only GitHub runners.
                if name in ('nvcuda.dll', 'vulkan-1.dll') or name.startswith(('api-ms-', 'ext-ms-')):
                    continue
                target = available.get(name)
                if target is None:
                    raise RuntimeError(f'{path.name} requires a missing DLL: {name}')
                if target.parent != system_dir:
                    pending.append(target)
    print(f'Verified {executable.name}: {len(checked)} bundled executable/DLL files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle_root', type=Path)
    args = parser.parse_args()
    for relative in ('llama/llama-server.exe', 'crispasr/crispasr.exe'):
        verify_native_runtime(args.bundle_root / relative, args.bundle_root)


if __name__ == '__main__':
    main()
