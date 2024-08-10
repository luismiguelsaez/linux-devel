import tarfile
import zipfile
import requests
from os.path import expanduser, isdir
from os import makedirs

packages = {
    "zoxide": {
        "type": "tar",
        "url": {
            "x86_64": "https://github.com/ajeetdsouza/zoxide/releases/download/v0.9.4/zoxide-0.9.4-x86_64-unknown-linux-musl.tar.gz",
            "arm64": "https://github.com/ajeetdsouza/zoxide/releases/download/v0.9.4/zoxide-0.9.4-armv7-unknown-linux-musleabihf.tar.gz",
        },
        "file": "zoxide",
    },
    "yazi": {
        "type": "zip",
        "url": {
            "x86_64": "https://github.com/sxyazi/yazi/releases/download/v0.3.0/yazi-x86_64-unknown-linux-gnu.zip",
            "arm64": "https://github.com/sxyazi/yazi/releases/download/v0.3.0/yazi-x86_64-unknown-linux-gnu.zip",
        },
        "file": "yazi",
    },
    "opentofu": {
        "type": "tar",
        "url": {
            "x86_64": "https://github.com/opentofu/opentofu/releases/download/v1.8.1/tofu_1.8.1_linux_amd64.tar.gz",
            "arm64": "https://github.com/opentofu/opentofu/releases/download/v1.8.1/tofu_1.8.1_linux_arm.tar.gz",
        },
        "file": "tofu",
    },
    "fzf": {
        "type": "tar",
        "url": {
            "x86_64": "https://github.com/junegunn/fzf/releases/download/v0.54.3/fzf-0.54.3-linux_amd64.tar.gz",
            "arm64": "https://github.com/junegunn/fzf/releases/download/v0.54.3/fzf-0.54.3-linux_armv7.tar.gz",
        },
        "file": "fzf",
    },
    "eza": {
        "type": "tar",
        "url": {
            "x86_64": "https://github.com/eza-community/eza/releases/download/v0.19.0/eza_x86_64-unknown-linux-musl.tar.gz",
            "arm64": "https://github.com/eza-community/eza/releases/download/v0.19.0/eza_aarch64-unknown-linux-gnu.tar.gz",
        },
        "file": "./eza",
    },
    "zellij": {
        "type": "tar",
        "url": {
            "x86_64": "https://github.com/zellij-org/zellij/releases/download/v0.40.1/zellij-x86_64-unknown-linux-musl.tar.gz",
            "arm64": "https://github.com/zellij-org/zellij/releases/download/v0.40.1/zellij-aarch64-unknown-linux-musl.tar.gz",
        },
        "file": "zellij",
    },
}

arch = "x86_64"
bin_path = expanduser("~/.local/bin")


def setup() -> None:
    if not isdir(bin_path):
        makedirs(bin_path)


def package_install_tar(pkg: str, file: str, dest: str) -> None:
    with tarfile.open(name=pkg, mode="r", bufsize=10240) as tar:
        if file not in tar.getnames():
            print(f"File [{file}] not found in archive")
        else:
            f = tar.extractfile(member=file)
            f_content = f.read()
            open(dest, "wb").write(f_content)


def package_install_zip(pkg: str, file: str, dest: str) -> None:
    with zipfile.ZipFile(file=pkg, mode="r") as zip:
        print(f"Installing zip file: {zip.namelist()}")
        with zip.open("yazi-x86_64-unknown-linux-gnu/yazi") as zip_file:
            open(dest, "wb").write(zip_file.read())


def package_download(url: str, output: str) -> None:
    with requests.get(
        url=url,
    ) as r:
        r.raise_for_status()
        with open(output, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def main():
    setup()

    for package in packages:
        print(f"Downloading package: {package}")
        tmp_file = packages[package]["url"][arch].split("/")[-1]
        package_download(
            url=packages[package]["url"][arch],
            output=f"/tmp/{tmp_file}",
        )
        if packages[package]["type"] == "tar":
            print(f"Installing tar package: {package}")
            package_install_tar(
                pkg=f"/tmp/{tmp_file}",
                file=packages[package]["file"],
                dest=f"{bin_path}/{packages[package]['file']}",
            )
        elif packages[package]["type"] == "zip":
            print(f"Installing zip package: {package}")
            package_install_zip(
                pkg=f"/tmp/{tmp_file}",
                file=packages[package]["file"],
                dest=f"{bin_path}/{packages[package]['file']}",
            )


if __name__ == "__main__":
    main()
