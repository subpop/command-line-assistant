from setuptools import find_packages, setup


def parse_requirements(filename):
    with open(filename, "r") as file:
        return file.read().splitlines()

setup(
    name="shellai",
    version="0.0.1",
    author="Andrea Waltlova",
    author_email="awaltlov@redhat.com",
    description="A simple wrapper to interact with RAG",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://gitlab.cee.redhat.com/rhel-lightspeed/enhanced-shell/shellai",
    packages=find_packages(),
    install_requires=parse_requirements("shellai/requirements.txt"),
    entry_points={
        'console_scripts': [
            'shellai = shellai.main:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.12',
)
