#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import os.path

def getConfigPath():
    if 'APPDATA' in os.environ:
        confighome = os.environ['APPDATA']
    elif 'XDG_CONFIG_HOME' in os.environ:
        confighome = os.environ['XDG_CONFIG_HOME']
    else:
        confighome = os.path.join(os.environ['HOME'], '.config')
    return os.path.join(confighome, 'bibtexvcs')

def saveDefaultDatabase(db):
    with open(getConfigPath(), 'wt') as configFile:
        configFile.write(db.directory)

def getDefaultDatabase():
    with open(getConfigPath(), 'rt') as configFile:
        directory = configFile.read()
    from bibtexvcs.database import Database
    return Database(directory)
    