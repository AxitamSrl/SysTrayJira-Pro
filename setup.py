from setuptools import setup, find_packages

setup(
    name="jira-tray-pro",
    version="1.0.0",
    description="SysTrayJira Pro — Premium Jira system tray with advanced features",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Regis Gilot",
    author_email="regis.gilot@axitam.eu",
    license="Apache-2.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pystray",
        "Pillow",
        "requests",
        "pyyaml",
    ],
    entry_points={
        "console_scripts": [
            "jira-tray-pro=jira_tray.app:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
