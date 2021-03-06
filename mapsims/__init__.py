# Licensed under a 3-clause BSD style license - see LICENSE.rst

# Packages may add whatever they like to this file, but
# should keep this content at the top.
# ----------------------------------------------------------------------------
from .channel_utils import Channel, parse_channels
from .noise import SONoiseSimulator
from .cmb import SOPrecomputedCMB, SOStandalonePrecomputedCMB
from .runner import MapSim, from_config, get_default_so_resolution

# ----------------------------------------------------------------------------

# Enforce Python version check during package import.
# This is the same check as the one at the top of setup.py
import sys

__minimum_python_version__ = "3.6"


class UnsupportedPythonError(Exception):
    pass


if sys.version_info < tuple(
    (int(val) for val in __minimum_python_version__.split("."))
):
    raise UnsupportedPythonError(
        "mapsims does not support Python < {}".format(__minimum_python_version__)
    )

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError


try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"
