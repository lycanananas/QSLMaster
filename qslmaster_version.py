import os
from importlib import metadata

APP_NAME = "QSLMaster"
SOURCE_VERSION = "1.5.3"


def get_version() -> str:
    version_from_env = os.getenv("QSLMASTER_VERSION")
    if version_from_env:
        return version_from_env

    try:
        return metadata.version("qslmaster")
    except metadata.PackageNotFoundError:
        return SOURCE_VERSION


def get_user_agent() -> str:
    return f"{APP_NAME}/{get_version()}"
