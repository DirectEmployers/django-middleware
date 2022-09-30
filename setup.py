from setuptools import find_packages, setup

setup(
    name="django-middleware",
    version="1.0.0",
    description="Reusable Django utilities for DE apps.",
    url="https://github.com/DirectEmployers/django-utils",
    license="Copyright © 2011-2022, DirectEmployers Association",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.8",
    install_requires=["django==3.2.*"],
)
