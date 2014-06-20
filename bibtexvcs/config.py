#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
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
def setDefaultDatabase(db):
    """Sets the default database."""
    if db.directory not in _config.sections():
        _config[db.directory] = {}
    for section in _config.sections():
        if _config.getboolean(section, 'default', fallback=False):
            del _config[section]['default']
    _config[db.directory]['default'] = 'yes'


@ensureInit
def getDefaultDatabase():
    """Return the default database, or None if the config file is empty."""
    from bibtexvcs.database import Database
    try:
        for section in _config.sections():
            if _config.getboolean(section, 'default', fallback=False):
                return Database(section)
        # fallback: open last in config file
        return Database(_config.sections[-1])
    except Exception as e:
        print(e)
        return None


@ensureInit
def setAuthInformation(db):
    """Set username / password information for the given database."""
    if db.directory not in _config.sections():
        _config[db.directory] = {}
    _config[db.directory]['username'] = db.vcs.username
    _config[db.directory]['password'] = db.vcs.password


@ensureInit
def getAuthInformation(db):
    """Return a pair of `(username, password)` for the given database, or ``None`` if it is not
    set.
    """
    try:
        return _config[db.directory]['username'], _config[db.directory]['password']
    except KeyError:
        return None


@atexit.register
def save():
    """Store the current configuration to disk."""
    if _config is not None:
        confdir = os.path.dirname(getConfigPath())
        if not os.path.exists(confdir):
            os.makedirs(confdir)
        with io.open(getConfigPath(), 'wt', encoding='UTF-8') as configfile:
            _config.write(configfile)
