#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import argparse, io

from bibtexvcs.database import Database


def export(args):
    if args.template:
        with io.open(args.template, 'r', encoding='UTF-8') as templateFile:
            templateString = templateFile.read()
    else:
        templateString = None
    output = args.db.export(templateString=templateString, docDir=args.docs)
    if args.output == '-':
        print(output)
    else:
        with io.open(args.output, 'wt', encoding='UTF-8') as outfile:
            outfile.write(output)


def check(args):
    from bibtexvcs import checks
    errors, warnings = checks.performDatabaseCheck(args.db)
    for err in errors:
        print('FAIL: {}'.format(err))
    for warn in warnings:
        print('WARN: {}'.format(warn))


def script():
    """Command-line script that allows to export a database and run checks."""
    desc = ('Command-line interface to the BibTeX VCS package. Can be used to run the GUI, run '
            'JabRef configured for a specified BibTeX VCS database, export a database using '
            'templates (e.g. HTML output), or run database sanity checks.')
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        '-d', '--database', metavar='DB',
        help='specify database root directory. If left out, the default database is used'
    )

    parser.add_argument('mode', choices=('gui', 'jabref', 'export', 'check'),
                        help='choose mode of operation (default: gui)',
                        default='gui',
                        nargs='?')

    exportGroup = parser.add_argument_group('exporting options (only in "export" mode)')
    exportGroup.add_argument('--template', help='template file')
    exportGroup.add_argument('--docs', help='documents root path')
    exportGroup.add_argument('output', nargs='?', help='output file')

    args = parser.parse_args()
    if args.mode == 'gui':
        import bibtexvcs.gui
        bibtexvcs.gui.run(args.database)
    else:
        # load database. We don't load it before starting the GUI because the GUI will display
        # a progress bar while loading the database by itself.
        if args.database:
            args.db = Database(args.database)
        else:
            args.db = Database.getDefault()
        if args.mode == 'export':
            export(args)
        elif args.mode == 'jabref':
            args.db.runJabref()
        elif args.mode == 'check':
            check(args)

if __name__ == '__main__':
    script()
