from __future__ import annotations

import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"

FILE_ENTRIES = [
    "SKILL.md",
    "config.example.json",
    "pyproject.toml",
    "uv.lock",
    "automation/arxiv-profile-digest.example.toml",
    "profiles/research-interest.example.json",
]

DIR_ENTRIES = [
    "src",
    "references",
    "automation/prompts",
    "reports/schema",
]


def _version() -> str:
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _copy_tree(src_rel: str, package_root: Path) -> None:
    src = REPO_ROOT / src_rel
    dst = package_root / src_rel
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _make_zip(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(source_dir.parent))


def _make_tar(source_dir: Path, tar_path: Path) -> None:
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(source_dir, arcname=source_dir.name)


def build() -> tuple[Path, Path, Path]:
    version = _version()
    package_name = f"research-assist-skill-v{version}"
    package_root = DIST_DIR / package_name
    zip_path = DIST_DIR / f"{package_name}.zip"
    tar_path = DIST_DIR / f"{package_name}.tar.gz"

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    for rel in FILE_ENTRIES:
        _copy_tree(rel, package_root)
    for rel in DIR_ENTRIES:
        _copy_tree(rel, package_root)

    install_src = REPO_ROOT / "scripts" / "distribution" / "install_skill.sh"
    install_dst = package_root / "install.sh"
    shutil.copy2(install_src, install_dst)
    install_dst.chmod(0o755)

    if zip_path.exists():
        zip_path.unlink()
    if tar_path.exists():
        tar_path.unlink()

    _make_zip(package_root, zip_path)
    _make_tar(package_root, tar_path)
    return package_root, zip_path, tar_path


def main() -> None:
    package_root, zip_path, tar_path = build()
    print(f"package_root={package_root}")
    print(f"zip={zip_path}")
    print(f"tar_gz={tar_path}")


if __name__ == "__main__":
    main()
