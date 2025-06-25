from setuptools import setup, find_packages
import os

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="killable-sudo",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Wrapper around sudo allowing killing of processes run with sudo",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/yourname/killable-sudo",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "killable-sudo=killable_sudo.main:main",
        ],
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.6",
)
