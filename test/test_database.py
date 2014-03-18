#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import unittest
from os.path import join, split

from bibtexvcs import database
from . import datadir

class TestDatabaseConfig(unittest.TestCase):

    def setUp(self):
        self.db = database.Database(join(datadir(), 'sampleDB'))

    def testConfValues(self):
        self.assertEqual(self.db.name, 'Example literature database managed by the bibtex VCS package')
        directory = split(self.db.directory)
        self.assertEqual(directory[-1], 'sampleDB')
        self.assertEqual(self.db.journalsName, 'journals.txt')
        self.assertEqual(self.db.bibfileName, 'sample.bib')


