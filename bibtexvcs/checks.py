#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from bibtexvcs.bibfile import MacroReference, MONTHS
import sys, inspect

def performDatabaseCheck(database):
    me = sys.modules[__name__]
    checks = [fun for fname, fun in inspect.getmembers(me, inspect.isfunction) if fname.startswith('check')]
    errors = []
    for check in checks:
        errors.extend(list(check(database)))
    return errors

class CheckFailed(Exception):
    pass

def checkMacros(database):
    """Check if all macros referenced in the database exist in its journals file."""
    bib = database.bibfile
    for entry in bib.values():
        for field, value in entry.items():
            if isinstance(value, MacroReference):
                if value.name in bib.macroDefinitions or value.name in database.journals:
                    continue
                if value.name in MONTHS:
                    continue
                yield CheckFailed("The macro '{m}' used for field '{f}' in bibtex "
                                  "entry '{e}' is defined neither in the database nor "
                                  "in the journals file."
                                  .format(f=field, m=value.name, e=entry.citekey))


def checkFileLinks(database):
    """Check that the files linked to in the database match those existing in the `documents`
    directory. Additionally, check that all documents are contained in the `documents` directory.
    """

    dbFilesSet = set(database.referencedDocuments())
    fsFilesSet = set(database.existingDocuments())

    if len(dbFilesSet - fsFilesSet) > 0:
        yield CheckFailed("The following file(s) are referenced in the bibtex file but do not "
                          "exist in the documents directory:\n{}"
                          .format("\n".join(dbFilesSet - fsFilesSet)))
    if len(fsFilesSet - dbFilesSet) > 0:
        yield CheckFailed("The following file(s) in the documents directory are not referenced by "
                          "any entry in the bibtex file:\n{}"
                          .format("\n".join(fsFilesSet - dbFilesSet)))


def checkASCIIFilenames(database):
    """Check that all file names are ASCII. This is sensible because non-ASCII file names lead
    to problems with most VCS systems.
    """
    for filename in database.existingDocuments():
        try:
            filename.encode('ascii')
        except UnicodeEncodeError:
            yield CheckFailed('The file name "{}" contains non-ASCII characters.'.format(filename))


MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def checkMonthMacros(database):
    """Checks that the ``month`` field only contains (proper) macros."""

    for entry in database.bibfile.values():
        if 'month' not in entry:
            continue
        month = entry['month']
        if isinstance(month, str):
            yield CheckFailed("Month field in entry '{e}' contains the string '{s}' instead "
                              "of a month macro.".format(e=entry.citekey, s=month))
        elif isinstance(month, MacroReference):
            if month.name not in MONTHS:
                yield CheckFailed("Invalid month macro '{}' used in entry '{}'"
                                 .format(month.name, entry.citekey))
        else:
            #  must be a list of macros
            if len(month) % 2 != 1:
                yield CheckFailed("Invalid month definition '{}' in '{}': Must be either a single "
                                 "month macro or of the format 'mar / apr'."
                                 .format(month, entry.citekey))
                continue
            separators = [ month[i] for i in range(1, len(month), 2) ]
            macros = [ month[i] for i in range(0, len(month), 2) ]
            for separator in separators:
                if separator.strip() != '/':
                    yield CheckFailed("Invalid month definition '{}' in '{}': Expected '/' but got "
                                      "'{}".format(month, entry.citekey, separator.strip()))
            for macro in macros:
                if not isinstance(macro, MacroReference) or macro.name not in MONTHS:
                    yield CheckFailed("Invalid month definition '{}' in '{}'"
                                      .format(month, entry.citekey))

def checkJabrefFileDirectory(database):
    identifier = 'jabref-meta: fileDirectory:'
    for comment in database.bibfile.comments:
        if comment.comment.startswith(identifier):
            if comment.comment[len(identifier):] != database.documents + ';':
                yield CheckFailed('JabRef fileDirectory field does not coincide with '
                                  'the configured one.')
