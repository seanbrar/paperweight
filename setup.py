# type: ignore
from setuptools import find_packages, setup

setup(
    name="paperweight",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pypdf",
        "python-dotenv",
        "PyYAML",
        "requests",
        "simplerllm",
        "tiktoken",
        "tenacity",
    ],
    entry_points={
        "console_scripts": [
            "paperweight=paperweight.main:main",
        ],
    },
    author="Sean Brar",
    description="Automatically retrieve, filter, and summarize recent academic papers from arXiv",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/seanbrar/paperweight",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
