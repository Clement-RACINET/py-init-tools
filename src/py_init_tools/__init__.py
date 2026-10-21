# Copyright (C) 2026 Clément RACINET
# SPDX-FileCopyrightText: 2026 Clément RACINET
#
# SPDX-License-Identifier: X11
"""Utilities to safely audit and generate Python package __init__.py files."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("py-init-tools")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
