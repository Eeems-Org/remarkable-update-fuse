from . import UpdateFS


def main():
    server = UpdateFS()
    server.parse(values=server, errex=1)
    server.main()


if __name__ == "__main__":
    main()
