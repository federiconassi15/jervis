from __future__ import annotations

import os

from setuptools import setup
from setuptools_rust import Binding, RustExtension


def rust_extensions():
    if os.environ.get("JERVIS_NO_RUST", "").lower() in {"1", "true", "yes"}:
        return []
    return [
        RustExtension(
            "jervis._fast",
            path="native/jervis_fast/Cargo.toml",
            binding=Binding.PyO3,
            optional=True,
            debug=False,
        )
    ]


setup(
    rust_extensions=rust_extensions(),
    zip_safe=False,
)
