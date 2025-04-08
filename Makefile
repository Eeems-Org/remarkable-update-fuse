.DEFAULT_GOAL := all
VERSION := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
PACKAGE := $(shell grep -m 1 name pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
CODEXCTL := https://github.com/Jayy001/codexctl/releases/download/1739239465/ubuntu-latest.zip
CODEXCTL_HASH := fdd36098ef7364cebe28b1343f39b7752eaa05f80f0fe956d04758c45396b2bc
FW_VERSION := 2.15.1.1189
FW_DATA := wVbHkgKisg-

OBJ := $(shell find ${PACKAGE} -type f)
OBJ += requirements.txt
OBJ += pyproject.toml
OBJ += README.md

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

ifeq ($(VENV_BIN_ACTIVATE),)
VENV_BIN_ACTIVATE := .venv/bin/activate
endif

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

dist/rmufuse: dist $(VENV_BIN_ACTIVATE) $(OBJ)
	. $(VENV_BIN_ACTIVATE); \
	python -m pip install \
	    --extra-index-url=https://wheels.eeems.codes/ \
	    wheel \
	    nuitka; \
	NUITKA_CACHE_DIR="$(realpath .)/.nuitka" \
	python -m nuitka \
	    --enable-plugin=pylint-warnings \
	    --enable-plugin=upx \
	    --warn-implicit-exceptions \
	    --onefile \
	    --lto=yes \
	    --include-package=google \
	    --noinclude-unittest-mode=allow \
	    --assume-yes-for-downloads \
	    --python-flag=-m \
	    --output-dir=dist \
	    --remove-output \
	    --output-filename=rmufuse \
	    remarkable_update_fuse

dist/rmufuse-portable: dist $(VENV_BIN_ACTIVATE) $(OBJ)
	. $(VENV_BIN_ACTIVATE); \
	python -m pip install \
	    --extra-index-url=https://wheels.eeems.codes/ \
	    wheel \
	    nuitka; \
	NUITKA_CACHE_DIR="$(realpath .)/.nuitka" \
	python -m nuitka \
	    --enable-plugin=pylint-warnings \
	    --enable-plugin=upx \
	    --warn-implicit-exceptions \
	    --onefile \
	    --lto=yes \
     --include-package=google \
	    --assume-yes-for-downloads \
	    --python-flag=-m \
	    --output-dir=dist \
	    --remove-output \
	    --output-filename=rmufuse-portable \
	    '--include-data-files=$(shell pkgconf --variable=libdir fuse)/libfuse.so=libfuse.so.2' \
	    '--include-data-files=$(shell pkgconf --variable=libdir libssl)/libssl.so=libssl.so.1' \
	    '--include-data-files=$(shell pkgconf --variable=libdir libcrypto)/libcrypto.so=libcrypto.so.3' \
	    remarkable_update_fuse
	patchelf --print-needed dist/rmufuse-portable

$(VENV_BIN_ACTIVATE): requirements.txt
	@echo "Setting up development virtual env in .venv"
	python -m venv .venv
	. $(VENV_BIN_ACTIVATE); \
	python -m pip install wheel ruff; \
	python -m pip install --extra-index-url=https://wheels.eeems.codes/ -r requirements.txt


.venv/codexctl.zip: $(VENV_BIN_ACTIVATE)
	curl -L "${CODEXCTL}" -o .venv/codexctl.zip

.venv/bin/codexctl: .venv/codexctl.zip
	@bash -c 'if ! sha256sum -c <(echo "${CODEXCTL_HASH} .venv/codexctl.zip") > /dev/null 2>&1; then \
	    echo "Hash mismatch, removing invalid codexctl.zip"; \
	    rm .venv/codexctl.zip; \
	    exit 1; \
	fi'
	unzip -n .venv/codexctl.zip -d .venv/bin
	chmod +x .venv/bin/codexctl

.venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed: .venv/bin/codexctl
	.venv/bin/codexctl download --hardware rm2 --out .venv ${FW_VERSION}

dev: $(VENV_BIN_ACTIVATE) .venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed  $(OBJ)
	if [ -d .venv/mnt ] && mountpoint -q .venv/mnt; then \
		umount -ql .venv/mnt; \
	fi
	mkdir -p .venv/mnt
	. $(VENV_BIN_ACTIVATE); \
	python -m remarkable_update_fuse \
	    -d \
	    -f \
	    .venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed \
	    .venv/mnt

test: $(VENV_BIN_ACTIVATE) .venv/${FW_VERSION}_reMarkable2-${FW_DATA}.signed $(OBJ)
	. $(VENV_BIN_ACTIVATE); \
	python test.py

executable: dist/rmufuse
	dist/rmufuse --help

portable: dist/rmufuse-portable

all: release

lint: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff check

lint-fix: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff check

format: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff format --diff

format-fix: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff format

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
	test \
	lint \
	lint-fix \
	format \
	format-fix
