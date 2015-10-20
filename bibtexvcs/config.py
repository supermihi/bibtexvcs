#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

"""
The :mod:`config <bibtexvcs.config>` module contains helpers for persisten configuration of BibTeX
VCS.
Currently, this allows to store VCS auth information and a default database to open at startup.
"""

from __future__ import division, print_function, unicode_literals
import configparser
import io
import os.path
import atexit


def getConfigPath():
    """Return the path of the configuration file. Defaults to ``~/.config/bibtexvcs`` on Unix,
    ``%APPDATA%/bibtexvcs`` on Windows, but also respects the ``XDG_CONFIG_HOME`` environment
    variable.
    """
    if 'APPDATA' in os.environ:
        confighome = os.environ['APPDATA']
    elif 'XDG_CONFIG_HOME' in os.environ:
        confighome = os.environ['XDG_CONFIG_HOME']
    else:
        confighome = os.path.join(os.environ['HOME'], '.config')
    return os.path.join(confighome, 'bibtexvcs')

_config = None


def init():
    """Initialize `_config` from the config file."""
    global _config
    _config = configparser.ConfigParser()
    _config.read(getConfigPath())


def ensureInit(func):
    """Decorator that calls :func:`init()` if necessary."""
    def newFunc(*args, **kwargs):
        global _config
        if _config is None:
            init()
        return func(*args, **kwargs)
    return newFunc


@ensureInit
def setDefaultDatabase(database):
    """Sets the default database."""
    if sectionKey(database) not in _config.sections():
        _config[sectionKey(database)] = {}
    for section in _config.sections():
        if _config.getboolean(section, 'default', fallback=False):
            del _config[section]['default']
    _config[sectionKey(database)]['default'] = 'yes'


@ensureInit
def getDefaultDirectory():
    """Return the directory of the default database, or ``None`` if it is not set.
    """
    for section in _config.sections():
        if _config.getboolean(section, 'default', fallback=False):
            return section
    if len(_config.sections()) > 0:
        # fallback: open last in config file (=last one added, most likely to be useful)
        return _config.sections[-1]
    return None


def sectionKey(database):
    """Return the key of the config section that corresponds to `database`.

    In current implementation, the database directory is used as key.
    """
    return database.directory


@ensureInit
def storeLogin(database, username, password):
    """Set username / password information for the given database."""
    key = sectionKey(database)
    if key not in _config.sections():
        _config[key] = {}
    _config[key]['username'] = username
    _config[key]['password'] = password


@ensureInit
def getLogin(database):
    """Return login information for the given database.

    Returns
    -------
    (username, password)
        Pair of username / password information. Both might be ``None`` if not stored.
    """
    try:
        section = _config[sectionKey(database)]
        return section.get('username'), section.get('password')
    except KeyError:
        return None, None


@atexit.register
def save():
    """Store the current configuration to disk."""
    if _config is not None:
        confdir = os.path.dirname(getConfigPath())
        if not os.path.exists(confdir):
            os.makedirs(confdir)
        with io.open(getConfigPath(), 'wt', encoding='UTF-8') as configfile:
            _config.write(configfile)
