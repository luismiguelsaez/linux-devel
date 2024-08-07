import tarfile
import requests
import io

packages = {
    "zoxide": {
        "type": "tar",
        "url": "https://github.com/ajeetdsouza/zoxide/releases/download/v0.9.4/zoxide-0.9.4-x86_64-unknown-linux-musl.tar.gz",
        "file": "zoxide",
    }
}


def package_install_tar(pkg: str, file: str, dest: str) -> None:
    with tarfile.open(pkg, "r") as tar:
        with tar.extractfile(member=file) as f:
            open(dest, "wb").write(f.read())


def package_download(url: str, output: str) -> None:
    with requests.get(
        url=url,
    ) as r:
        r.raise_for_status()
        with open(output, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def main():
    for package in packages:
        print(f"Downloading package: {package}")
        tmp_file = packages[package]["url"].split("/")[-1]
        package_download(
            url=packages[package]["url"],
            output=f"/tmp/{tmp_file}",
        )
        package_install_tar(
            pkg=f"/tmp/{tmp_file}",
            file=packages[package]["file"],
            dest=f"/tmp/{packages[package]['file']}",
        )


if __name__ == "__main__":
    main()
