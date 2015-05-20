#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

"""
The :mod:`checks` module defines a framework for defining and running automated *checks* on a
bibtexvcs
database.

Checks define certain constraints on the database related to consistency or other regulations.
For instance, a default check ensures that every macro that is used in the BibTeX file is defined
either in the bib file or in the list of journals.

Custom checks can be added per database by creating a module ``checks.py`` in the main database
directory. In that file, each check should be implemented as a function decorated with the
:func:`databaseCheck` decorator that takes the check's description as an argument. The check
function needs to act as a generator that yields :class:`CheckFailed` or :class:`CheckWarning`
instances in case of failures or warnings. An example file might look like this (contains a check
ensuring that every *journal* or *inproceedings* entry is a macro::

    from bibtexvcs.checks import CheckFailed, CheckWarning, databaseCheck
    from bibtexvcs.bibfile import MacroReference

    @databaseCheck('only macros in journals')
    def checkMacrosInJournals(database):
        for entry in database.bibfile.values():
            for field in ('inproceedings', 'journal'):
                if field in entry and not isinstance(entry[field], MacroReference):
                    yield CheckFailed('Entry "{}" has a non-macro {} field "{}"'
                                      .format(entry.citekey, field, entry[field]))
"""


from __future__ import division, print_function, unicode_literals
import os.path
import sys
import inspect
import imp
from bibtexvcs.bibfile import MacroReference, MONTHS


def performDatabaseCheck(database, exclude=[]):
    me = sys.modules[__name__]
    checks = {fun.checkName: fun for fname, fun in inspect.getmembers(me, inspect.isfunction)
                                 if hasattr(fun, 'checkName')}
    if os.path.exists(database.checksPath):
        localChecks = imp.load_source('checks', database.checksPath)
        for fname, fun in inspect.getmembers(localChecks, inspect.isfunction):
            if hasattr(fun, 'checkName'):
                checks[fun.checkName] = fun
    errors = []
    warnings = []

    for checkName, check in checks.items():
        if checkName not in exclude:
            for ans in check(database):
                if isinstance(ans, CheckFailed):
                    errors.append(ans)
                else:
                    warnings.append(ans)
    return errors, warnings


class CheckFailed(Exception):
    pass


class CheckWarning(Warning):
    pass


def databaseCheck(name):
    """Function decorator for database checks.

    :param name: a (unique) description text for the check.
    """
    def wrap(func):
        func.checkName = name
        return func
    return wrap


@databaseCheck('macro references')
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


@databaseCheck('file links')
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


@databaseCheck('ASCII filenames')
def checkASCIIFilenames(database):
    """Check that all file names are ASCII. This is sensible because non-ASCII file names lead
    to problems with most VCS systems.
    """
    for filename in database.existingDocuments():
        try:
            filename.encode('ascii')
        except UnicodeEncodeError:
            yield CheckFailed('The file name "{}" contains non-ASCII characters.'.format(filename))


@databaseCheck('month macros')
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


@databaseCheck('jabref file directory')
def checkJabrefFileDirectory(database):
    identifier = 'jabref-meta: fileDirectory:'
    for comment in database.bibfile.comments:
        if comment.comment.startswith(identifier):
            if comment.comment[len(identifier):] != database.documents + ';':
                yield CheckFailed('JabRef fileDirectory field does not coincide with '
                                  'the configured one.')


@databaseCheck('required BibTeX fields')
def checkRequiredFields(database):
    """Checks that all required fields exist for each entry."""
    requiredFields = {
        'article'      : ('author', 'title', 'journal', 'year'),
        'book'         : (('author', 'editor'), 'title', 'publisher', 'year'),
        'booklet'      : ('title'),
        'incollection' : ('author', 'title', 'booktitle', 'publisher', 'year'),
        'inproceedings': ('author', 'title', 'booktitle', 'year'),
        'mastersthesis': ('author', 'title', 'school', 'year'),
        'phdthesis'    : ('author', 'title', 'school', 'year'),
        'misc'         : (),
        'techreport'   : ('author', 'title', 'institution', 'year'),
        'unpublished'  : ('author', 'title', 'note'),
        'online'       : (('author', 'editor'), 'title', 'year', 'url')
    }
    for entry in database.bibfile.values():
        if entry.entrytype not in requiredFields:
            yield CheckWarning('Entry "{}": Required fields for type "{}" unknown'
                               .format(entry.citekey, entry.entrytype))
        else:
            for req in requiredFields[entry.entrytype]:
                if isinstance(req, tuple):
                    if not any(subReq in entry for subReq in req):
                        yield CheckFailed('Entry "{}" of type "{}" requires one of the fields: {}'
                                          .format(entry.citekey, entry.entrytype, ', '.join(req)))
                elif req not in entry:
                    yield CheckFailed('Entry "{}" of type "{}" requires field "{}"'
                                      .format(entry.citekey, entry.entrytype, req))


@databaseCheck('entry owners')
def checkOwnerExists(database):
    for entry in database.bibfile.values():
        if 'owner' not in entry:
            yield CheckFailed('Entry "{}" has no owner.'.format(entry.citekey))


@databaseCheck('marked entries')
def checkNoMarkedEntry(database):
    for entry in database.bibfile.values():
        if '__markedentry' in entry:
            yield CheckFailed('Entry "{}" is marked in jabref:\n{}'
                              .format(entry.citekey, entry['__markedentry']))