#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

"""BibTeX VCS main package."""
from __future__ import division, print_function, unicode_literals
import sys

__version__ = '2014.10'


def pypiVersion():
    """Return the current version of this package on PyPI."""
    if sys.version_info.major == 2:
        import urllib2
        urlopen = urllib2.urlopen
    else:
        import urllib.request
        urlopen = urllib.request.urlopen
    with urlopen('https://pypi.python.org/pypi/bibtexvcs/json') as f:
        data = f.read().decode()
    import json
    decoded = json.loads(data)
    return decoded['info']['version']
