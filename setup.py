"""Setup script for zgdk project."""

from setuptools import find_packages, setup

setup(
    name="zgdk",
    version="0.1.0",
    description="zaGadka Discord Bot",
    packages=find_packages(),
    python_requires=">=3.10",
    package_dir={"": "."},
    include_package_data=True,
)