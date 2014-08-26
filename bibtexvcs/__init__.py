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

__version__ = '2014.18'


def pypiVersion():
    """Return the current version of this package on PyPI."""
    if sys.version_info.major == 2:
        import urllib2
        from urllib2 import URLError
        urlopen = urllib2.urlopen
    else:
        import urllib.request
        from urllib.error import URLError
        urlopen = urllib.request.urlopen
    try:
        data = urlopen('https://pypi.python.org/pypi/bibtexvcs/json').read().decode()
    except URLError:
        return None
    import json
    decoded = json.loads(data)
    return decoded['info']['version']
