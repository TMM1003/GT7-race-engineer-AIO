from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "GT7 Machine Learning Tool"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return project_root()


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def user_documents_dir() -> Path:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            result = ctypes.windll.shell32.SHGetFolderPathW(
                None,
                5,  # CSIDL_PERSONAL
                None,
                0,
                buf,
            )
            if result == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            pass

        userprofile = os.getenv("USERPROFILE")
        if userprofile:
            return Path(userprofile) / "Documents"

    docs = Path.home() / "Documents"
    return docs if docs.exists() else Path.home()


def user_data_root() -> Path:
    override = (
        os.getenv("GT7_MACHINE_LEARNING_TOOL_HOME", "").strip()
        or os.getenv("GT7_RACE_ENGINEER_HOME", "").strip()
    )
    if override:
        return Path(override).expanduser()
    return user_documents_dir() / APP_NAME


def default_runs_dir() -> Path:
    return user_data_root() / "data" / "runs"


def ensure_user_data_dirs() -> None:
    default_runs_dir().mkdir(parents=True, exist_ok=True)
