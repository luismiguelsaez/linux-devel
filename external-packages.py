import tarfile
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
    setup()

    for package in packages:
        print(f"Downloading package: {package}")
        tmp_file = packages[package]["url"][arch].split("/")[-1]
        package_download(
            url=packages[package]["url"][arch],
            output=f"/tmp/{tmp_file}",
        )
        package_install_tar(
            pkg=f"/tmp/{tmp_file}",
            file=packages[package]["file"],
            dest=f"{bin_path}/{packages[package]['file']}",
        )


if __name__ == "__main__":
    main()
