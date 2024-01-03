from setuptools import find_packages, setup

setup(
    name="django-middleware",
    version="4.2",
    description="Reusable Django utilities for DE apps.",
    url="https://github.com/DirectEmployers/django-middleware",
    license="Copyright © 2011-2024, DirectEmployers Association",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.11",
    install_requires=["django>=4.2"],
)
