import os


def write_file(tmp_dir, file_name, code):
    file_path = os.path.join(tmp_dir, file_name)
    with open(file_path, "w") as fh:
        fh.write(code)
        return file_path


def normalized_stderr(stderr_bytes):
    """
    Filter out environment noise from stderr (e.g., setuptools/pkg_resources
    deprecation notices emitted by console script wrappers) to keep tests
    stable across Python versions and packaging toolchains.
    """
    try:
        lines = stderr_bytes.decode().splitlines()
    except Exception:
        # Fallback: treat as no stderr if decoding fails unexpectedly
        return []

    def is_noise(line: str) -> bool:
        l = line.strip().lower()
        # Known noisy sources: setuptools/pkg_resources deprecation notices
        if "pkg_resources" in l or "setuptools" in l:
            return True
        return False

    return [line for line in lines if not is_noise(line)]
