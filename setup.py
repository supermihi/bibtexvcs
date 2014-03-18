#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation
from __future__ import division, print_function, unicode_literals
import io, re, os, sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
# From PyPA's sampleproject (https://github.com/pypa/sampleproject).
with io.open(os.path.join(here, 'bibtexvcs', '__init__.py'), 'r', encoding='UTF-8') as f:
    version_file = f.read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        version = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string.")

with io.open(os.path.join(here, 'README.rst'), encoding='UTF-8') as f:
    long_description = f.read()

requires = ['pyparsing']
if sys.version_info.major == 2:
    # depend on backported packages
    requires.append('futures')
    requires.append('configparser')


setup(
    name='bibtexvcs',
    version=version,
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
      'Programming Language :: Python :: 2.7',
      'Programming Language :: Python :: 3',
      'Topic :: Database :: Front-Ends',
    ],
    license='GPL3',
    keywords='bibliography bibtex jabref',
    packages=find_packages(),
    install_requires=requires,
    entry_points={ 'gui_scripts'     : ['btvcs = bibtexvcs.gui:run'],
                   'console_scripts' : ['cbtvcs = bibtexvcs.script:script'] },
    include_package_data=True,
    test_suite='test'
)
