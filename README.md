[![remarkable_update_fuse on PyPI](https://img.shields.io/pypi/v/remarkable_update_fuse)](https://pypi.org/project/remarkable_update_fuse)

# reMarkable Update FUSE
Mount remarkable update files using FUSE

## Usage

```bash
pip install remarkable_update_fuse
mkdir /mnt/signed /mnt/image
rmufuse path/to/update_file.signed /mnt/signed
```

## Known Issues

- Will report checksum errors for Directory inode, even though they are fine
- Will report checksum errors for extent headers, even though they are fine

## Building
Dependencies:
- curl
- protoc
- python
- python-build
- python-pip
- python-pipx
- python-venv
- python-wheel

```bash
make # Build wheel and sdist packages in dist/
make wheel # Build wheel package in dist/
make sdist # Build sdist package in dist/
make dev # Test mounting 2.15.1.1189 to .venv/mnt
make test # Run automated tests
make install # Build wheel and install it with pipx or pip install --user
```
