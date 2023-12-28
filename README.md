[![remarkable_update_fuse on PyPI](https://img.shields.io/pypi/v/remarkable_update_fuse)](https://pypi.org/project/remarkable_update_fuse)

# reMarkable Update FUSE
Mount remarkable update files using FUSE

```bash
pip install remarkable_update_fuse
mkdir /mnt/signed /mnt/image

# Fully userspace
rmufuse path/to/update_file.signed /mnt/signed
ext4fuse /mnt/signed/image.ext4 /mnt/image

# Using loopback
# Ensure /etc/fuse.conf has user_allow_other
rmufuse -o allow_root path/to/update_file.signed /mnt/signed
mount /mnt/signed/image.ext4 /mnt/image
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
