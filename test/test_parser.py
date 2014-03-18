#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import unittest

from bibtexvcs import bibfile, parser

bibtext = """This is an implicit comment.
@PREAMBLE{"This is the preamble."}

@ArtiCLe{ArticleKey,
    author = {Helmling, Michael J.},
    title  = {A bibtex database under revision control}
}
"""
class TestBasicParsing(unittest.TestCase):

    def setUp(self):
        self.bibfile = bibfile.BibFile(bibstring=bibtext)

    def testImplicitComment(self):
        self.assertGreater(len(self.bibfile.comments), 0)
        self.assertIsInstance(self.bibfile.comments[0], bibfile.ImplicitComment)
        self.assertEqual(self.bibfile.comments[0].comment,
                         "This is an implicit comment.\n")

    def testEntry(self):
        self.assertGreater(len(self.bibfile), 0)
        self.assertIn('ArticleKey', self.bibfile, 'ArticleKey not found in {}'.format(list(self.bibfile.keys())))
        entry = self.bibfile['ArticleKey']
        self.assertEqual(entry.entrytype, 'article')


class TestNameParsing(unittest.TestCase):

    def parse(self, name):
        return parser.name.parseString(name, parseAll=True)[0]

    def testNobility(self):
        name = "van der Zalm, E."
        parsed = self.parse(name)
        self.assertEqual(parsed.nobility, "van der")

        name = "van Emde Boas, P."
        parsed = self.parse(name)
        self.assertEqual(parsed.last, "Emde Boas")
        self.assertEqual(parsed.nobility, "van")
        self.assertEqual(parsed.first, "P.")

    def testCommaName(self):
        parsed = self.parse("Helmling, Michael")
        self.assertEqual(parsed.first, "Michael")
        self.assertEqual(parsed.last, "Helmling")
        self.assertIsNone(parsed.nobility)
        self.assertIsNone(parsed.suffix)

        parsed = self.parse("Forney, Jr., David G.")
        self.assertEqual(parsed.first, "David G.")
        self.assertEqual(parsed.suffix, "Jr.")
        self.assertEqual(parsed.last, "Forney")

    def testLiteralName(self):
        parsed = self.parse("Michael Jakob Helmling")
        self.assertEqual(parsed.last, "Helmling")
        self.assertEqual(parsed.first, "Michael Jakob")

    def testCurlyName(self):
        parsed = self.parse("{Ministry of Truth and Justice}")
        self.assertEqual(parsed.last, "Ministry of Truth and Justice")


class TestNamesListParsing(unittest.TestCase):

    def parse(self, namesList):
        return parser.namesList.parseString(namesList, parseAll=True)

    def testLiteralAnd(self):
        parsed = self.parse("{{Ministry of Truth and Justice} and Helmling, Michael}")
        self.assertEqual(len(parsed), 2)
        ministry = parsed[0]
        self.assertEqual(ministry.last, "Ministry of Truth and Justice")
        me = parsed[1]
        self.assertEqual(me.last, "Helmling")
