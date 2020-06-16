import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pollscore-nbruin",
    version="0.0.1",
    author="Nils Bruin",
    author_email="nbruin@sfu.ca",
    license="MIT",
    description="Score and process online poll reports for upload in a course management system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages(),
    install_requires=[
        'pandas',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': ['pollscore=pollscore.pollscore:main'],
    },
)

