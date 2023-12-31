[![remarkable_update_fuse on PyPI](https://img.shields.io/pypi/v/remarkable_update_fuse)](https://pypi.org/project/remarkable_update_fuse)

# reMarkable Update FUSE
Mount remarkable update files using FUSE

## Usage

```bash
pip install remarkable_update_fuse
mkdir /mnt/signed /mnt/image
rmufuse path/to/update_file.signed /mnt/signed
```

## Programatic Usage

```python
from ext4 import Volume
from remarkable_update_fuse import UpdateImage

image = UpdateImage("path/to/update/file.signed")

# Extract raw ext4 image
with open("image.ext4", "wb") as f:
    f.write(image.read())

# Extract specific file
volume = Volume(image, offset=0)
inode = volume.root.get_inode("etc", "version")
with open("version", "wb") as f:
    f.write(inode.open_read().read())
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
```
