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

## Programatic Usage

```python
from ext4 import Volume
from remarkable_update_fuse import UpdateImage

image = UpdateImage("path/to/update/file.signed")

# Extract raw ext4 image
with open("image.ext4", "wb") as f:
    f.write(image.read())

# Extract specific file
volume = Volume(image)
inode = volume.inode_at("etc", "version")
with open("version", "wb") as f:
    f.write(inode.open().read())
```

## Building
Dependencies:
- curl
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
make install # Build wheel and install it with pipx or pip install --user
make executable # Build a standalone executable
make portable # Build a standalone executable with some extra dependencies embedded
```

### Building for the reMarkable (Or really any linux/arm/v7 device)

The same as above, but use `./make_for_remarkable.sh` instead of `make`. This requires docker to be installed.
