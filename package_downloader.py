from ctypes import ArgumentError
import logging
import os
import shutil
import subprocess
import glob
import tarfile
import zipfile


# ------------------------------------------------------------
# Archive discovery
# ------------------------------------------------------------
ARCHIVE_PATTERNS = ("*.whl", "*.tar.gz", "*.zip")


# ------------------------------------------------------------
# Path safety (Zip Slip protection)
# ------------------------------------------------------------
def is_safe_path(base_dir: str, target_path: str) -> bool:
    base_dir = os.path.abspath(base_dir)
    target_path = os.path.abspath(target_path)
    return os.path.commonpath([base_dir, target_path]) == base_dir


def find_archive(target_dir: str) -> str | None:
    for pattern in ARCHIVE_PATTERNS:
        matches = glob.glob(os.path.join(target_dir, pattern))
        if matches:
            return matches[0]
    return None


# ------------------------------------------------------------
# Safe extraction helpers
# ------------------------------------------------------------
def extract_zip(path: str, target_dir: str, logger: logging.Logger) -> bool:
    with zipfile.ZipFile(path) as zf:
        for member in zf.infolist():
            dest = os.path.join(target_dir, member.filename)
            if not is_safe_path(target_dir, dest):
                logger.error("Security Alert: Zip Slip attempt detected in %s", member.filename)
                return False
            zf.extract(member, target_dir)
    return True


def extract_tar(path: str, target_dir: str, logger: logging.Logger) -> bool:
    with tarfile.open(path, "r:gz") as tf:
        if hasattr(tarfile, "data_filter"):  # Python 3.12+
            tf.extractall(target_dir, filter="data")
            return True

        for member in tf.getmembers():
            dest = os.path.join(target_dir, member.name)
            if not is_safe_path(target_dir, dest):
                logger.error("Security Alert: Zip Slip attempt detected in %s", member.name)
                return False
            tf.extract(member, target_dir)

    return True


# ------------------------------------------------------------
# Post-extraction cleanup
# ------------------------------------------------------------
def remove_dist_info(target_dir: str) -> None:
    for path in glob.glob(os.path.join(target_dir, "*.dist-info")):
        shutil.rmtree(path, ignore_errors=True)


def flatten_single_directory(target_dir: str, logger: logging.Logger) -> None:
    entries = [
        e
        for e in os.listdir(target_dir)
        if e not in ("__pycache__", "src") and not e.endswith(".dist-info")
    ]

    if len(entries) != 1:
        return

    inner = os.path.join(target_dir, entries[0])
    if not os.path.isdir(inner):
        return

    logger.info("Flattening archive folder: %s", inner)
    for item in os.listdir(inner):
        shutil.move(os.path.join(inner, item), target_dir)
    os.rmdir(inner)


def hoist_src_layout(target_dir: str, logger: logging.Logger) -> None:
    src_dir = os.path.join(target_dir, "src")
    if not os.path.isdir(src_dir):
        return

    logger.info("Detected src layout in %s", target_dir)
    for item in os.listdir(src_dir):
        shutil.move(os.path.join(src_dir, item), target_dir)
    shutil.rmtree(src_dir)


def hoist_single_package(target_dir: str, logger: logging.Logger) -> None:
    subdirs = [
        d
        for d in os.listdir(target_dir)
        if os.path.isdir(os.path.join(target_dir, d)) and d != "__pycache__"
    ]

    if len(subdirs) != 1:
        return

    pkg_dir = os.path.join(target_dir, subdirs[0])
    if not os.path.exists(os.path.join(pkg_dir, "__init__.py")):
        return

    logger.info("Hoisting package %s → %s", pkg_dir, target_dir)

    for item in os.listdir(pkg_dir):
        src = os.path.join(pkg_dir, item)
        dst = os.path.join(target_dir, item)

        if os.path.exists(dst):
            shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)

        shutil.move(src, dst)

    os.rmdir(pkg_dir)


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
def extract_package_files(logger: logging.Logger, target_dir: str) -> bool:
    archive = find_archive(target_dir)
    if not archive:
        logger.info("No archive found to extract.")
        return False

    logger.info("Extracting archive: %s", archive)

    try:
        if archive.endswith((".whl", ".zip")):
            ok = extract_zip(archive, target_dir, logger)
        else:
            ok = extract_tar(archive, target_dir, logger)

        if not ok:
            return False

    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        return False

    os.remove(archive)

    remove_dist_info(target_dir)
    flatten_single_directory(target_dir, logger)
    hoist_src_layout(target_dir, logger)
    hoist_single_package(target_dir, logger)

    logger.info(
        "Extraction complete (version preserved at %s)",
        os.path.basename(target_dir),
    )
    return True


def download_package(
    logger: logging.Logger,
    package_dir: str,
    name: str,
    version: str,
) -> bool:
    if not version:
        raise ArgumentError("Please provide a version")

    is_vcs = version.startswith(("git+", "github+"))
    ref = version.rsplit("@", 1)[-1] if is_vcs else version.replace(".", "_")
    requirement = version if is_vcs else f"{name}=={version}"

    target_dir = os.path.join(package_dir, f"{name}@{ref}")
    os.makedirs(target_dir, exist_ok=True)

    args = [
        "uv",
        "pip",
        "install" if is_vcs else "download",
        requirement,
        "--target" if is_vcs else "--dest",
        target_dir,
        "--no-deps",
    ]

    logger.info("Downloading into %s ...", target_dir)

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Download failed: %s", result.stderr)
        return False

    return True if is_vcs else extract_package_files(logger, target_dir)
