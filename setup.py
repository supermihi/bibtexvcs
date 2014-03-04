#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import re, os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))


def find_version(*file_paths):
    # From PyPA's sampleproject (https://github.com/pypa/sampleproject).
    with open(os.path.join(here, *file_paths), 'r') as f:
        version_file = f.read()

    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


with open(os.path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    long_description = f.read()

    
setup(
    name='bibtexvcs',
    version=find_version('bibtexvcs', '__init__.py'),
    description="a Python package for managing a BibTeX database and related documents",
    long_description=long_description,
    url='http://github.com/supermihi/bibtevxcs',
    author='Michael Helmling',
    author_email='michaelhelmling@posteo.de',
    classifiers=[
      'Development Status :: 3 - Alpha',
      'Intended Audience :: Science/Research',
      'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
      'Operating System :: OS Independent',
      'Programming Language :: Python :: 3.3',
      'Topic :: Database'
    ],
    license='GPL3',
    keywords='bibliography bibtex jabref',
    packages=find_packages(),
    install_requires=["pyparsing"],
)
