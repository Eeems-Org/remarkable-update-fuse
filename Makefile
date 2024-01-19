.DEFAULT_GOAL := all
VERSION := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
PACKAGE := $(shell grep -m 1 name pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
CODEXCTL := https://github.com/Jayy001/codexctl/releases/download/1703028363/ubuntu-latest.zip
CODEXCTL_HASH := 5c3aa5f264f4ae95de6e259eb8d5da8f0d9c2d7eb3710adb0cf53bcb72dcb79a
FW_VERSION := 2.15.1.1189
FW_DATA := wVbHkgKisg-

PROTO_SOURCE := $(shell find protobuf -type f -name '*.proto')
PROTO_OBJ := $(addprefix $(PACKAGE),$(PROTO_SOURCE:%.proto=%_pb2.py))

FUSE_FOLDER := $(shell pkgconf --variable=libdir fuse)

OBJ := $(shell find ${PACKAGE} -type f)
OBJ += requirements.txt
OBJ += pyproject.toml
OBJ += README.md
OBJ += $(PROTO_OBJ)

define PLATFORM_SCRIPT
from sysconfig import get_platform
print(get_platform().replace('-', '_'), end="")
endef
export PLATFORM_SCRIPT
PLATFORM := $(shell python -c "$$PLATFORM_SCRIPT")

define ABI_SCRIPT
def main():
    try:
        from wheel.pep425tags import get_abi_tag
        print(get_abi_tag(), end="")
        return
    except ModuleNotFoundError:
        pass

    try:
        from wheel.vendored.packaging import tags
    except ModuleNotFoundError:
        from packaging import tags

    name=tags.interpreter_name()
    version=tags.interpreter_version()
    print(f"{name}{version}", end="")

main()
endef
export ABI_SCRIPT
ABI := $(shell python -c "$$ABI_SCRIPT")

clean:
	if [ -d .venv/mnt ] && mountpoint -q .venv/mnt; then \
		umount -ql .venv/mnt; \
	fi
	git clean --force -dX

build: wheel

release: wheel sdist

install: wheel
	if type pipx > /dev/null; then \
	    pipx install \
	        --force \
	        dist/${PACKAGE}-${VERSION}-${ABI}-${ABI}-${PLATFORM}.whl; \
	else \
	    pip install \
	        --user \
	        --force-reinstall \
	        --no-index \
	        --find-links=dist \
	        ${PACKAGE}; \
	fi

sdist: dist/${PACKAGE}-${VERSION}.tar.gz

wheel: dist/${PACKAGE}-${VERSION}-${ABI}-${ABI}-${PLATFORM}.whl

dist:
	mkdir -p dist

dist/${PACKAGE}-${VERSION}.tar.gz: dist $(OBJ)
	python -m build --sdist

dist/${PACKAGE}-${VERSION}-${ABI}-${ABI}-${PLATFORM}.whl: dist $(OBJ)
	python -m build --wheel


dist/rmufuse: dist .venv/bin/activate $(OBJ)
	. .venv/bin/activate; \
	python -m pip install \
	    --extra-index-url=https://wheels.eeems.codes/ \
	    wheel \
	    nuitka; \
	NUITKA_CACHE_DIR="$(realpath .)/.nuitka" \
	nuitka3 \
	    --enable-plugin=pylint-warnings \
	    --enable-plugin=upx \
	    --warn-implicit-exceptions \
	    --onefile \
	    --lto=yes \
	    --assume-yes-for-downloads \
	    --python-flag=-m \
	    --output-dir=dist \
	    --remove-output \
	    --output-filename=rmufuse \
	    remarkable_update_fuse

dist/rmufuse-portable: dist .venv/bin/activate $(OBJ)
	. .venv/bin/activate; \
	python -m pip install \
	    --extra-index-url=https://wheels.eeems.codes/ \
	    wheel \
	    nuitka; \
	NUITKA_CACHE_DIR="$(realpath .)/.nuitka" \
	nuitka3 \
	    --enable-plugin=pylint-warnings \
	    --enable-plugin=upx \
	    --warn-implicit-exceptions \
	    --onefile \
	    --lto=yes \
	    --assume-yes-for-downloads \
	    --python-flag=-m \
	    --output-dir=dist \
	    --remove-output \
	    --output-filename=rmufuse-portable \
	    '--include-data-files=${FUSE_FOLDER}/libfuse.so.2.*=libfuse.so.2' \
	    remarkable_update_fuse
	patchelf dist/rmufuse

.venv/bin/activate: requirements.txt
	@echo "Setting up development virtual env in .venv"
	python -m venv .venv
	. .venv/bin/activate; \
	python -m pip install --extra-index-url=https://wheels.eeems.codes/ -r requirements.txt


.venv/codexctl.zip: .venv/bin/activate
	curl -L "${CODEXCTL}" -o .venv/codexctl.zip

.venv/bin/codexctl.bin: .venv/codexctl.zip
	@bash -c 'if ! sha256sum -c <(echo "${CODEXCTL_HASH} .venv/codexctl.zip") > /dev/null 2>&1; then \
	    echo "Hash mismatch, removing invalid codexctl.zip"; \
	    rm .venv/codexctl.zip; \
	    exit 1; \
	fi'
	unzip -n .venv/codexctl.zip -d .venv/bin
	chmod +x .venv/bin/codexctl.bin

.venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed: .venv/bin/codexctl.bin
	.venv/bin/codexctl.bin download --out .venv ${FW_VERSION}


$(PROTO_OBJ): $(PROTO_SOURCE)
	protoc \
	    --python_out=$(PACKAGE) \
	    --proto_path=protobuf \
	    $(PROTO_SOURCE)

dev: .venv/bin/activate .venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed  $(OBJ)
	if [ -d .venv/mnt ] && mountpoint -q .venv/mnt; then \
		umount -ql .venv/mnt; \
	fi
	mkdir -p .venv/mnt
	. .venv/bin/activate; \
	python -m remarkable_update_fuse \
	    -d \
	    -f \
	    .venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed \
	    .venv/mnt

test: .venv/bin/activate .venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed $(OBJ)
	. .venv/bin/activate; \
	python test.py

executable: dist/rmufuse
	dist/rmufuse --help

portable: dist/rmufuse-portable

all: release

.PHONY: \
	all \
	build \
	clean \
	dev \
	executable \
	portable \
	install \
	release \
	sdist \
	wheel \
	test
