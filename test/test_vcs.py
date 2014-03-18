#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import unittest
from os.path import join
import os

from bibtexvcs import vcs
from . import tmpDatabase, tmpClonedDatabase

class TestMercurial(unittest.TestCase):

    def testBasicVCS(self):
        with tmpDatabase() as db:
            self.assertTrue(db.vcs.localChanges())
            db.vcs.commit()
            self.assertFalse(db.vcs.localChanges())
            with open(join(db.documentsPath, "newTestDoc.pdf"), 'wt') as f:
                f.write('bla')
            os.remove(join(db.documentsPath, 'emptyDoc.pdf'))
            self.assertTrue(db.vcs.localChanges())
            db.vcs.commit()
            self.assertFalse(db.vcs.localChanges())

    def testRemoteVCS(self):
        with tmpDatabase() as _db:
            with tmpClonedDatabase(_db.directory) as db:
                self.assertEqual(len(os.listdir(db.documentsPath)), 1)
                with open(join(db.documentsPath, 'new1.pdf'), 'wt') as f:
                    f.write('bla')
                with open(join(db.documentsPath, 'new2.pdf'), 'wt') as f:
                    f.write('blub')
                self.assertTrue(db.vcs.localChanges())
                db.vcs.commit()
                _db.vcs.callHg('update')
                os.remove(join(_db.documentsPath, 'new2.pdf'))
                _db.vcs.commit()
                self.assertTrue(db.vcs.update())
                self.assertFalse(db.vcs.update())
                with open(db.journalsPath, 'at') as f:
                    f.write('x')
                with open(_db.journalsPath, 'at') as f:
                    f.write('y')
                self.assertTrue(_db.vcs.localChanges())
                _db.vcs.commit()
                self.assertRaises(vcs.MergeConflict, db.vcs.update)

