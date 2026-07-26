"""Version helper — single accessor for the package version (keeps imports tidy)."""
from mindbot_pipeline import __version__

def get_version() -> str:
    """Returns the current version of the mindbot_pipeline package."""
    return __version__
