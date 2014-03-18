#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import argparse

from bibtexvcs.database import Database
from bibtexvcs import config

def export(args):
    if args.template:
        with open(args.template, 'r', encoding='UTF-8') as templateFile:
            templateString = templateFile.read()
    else:
        templateString = None
    output = args.db.export(templateString=templateString, docDir=args.docs)
    with open(args.output, 'wt', encoding='UTF-8') as outfile:
        outfile.write(output)

def script():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--database', metavar='DB', help='database root directory')
    subparsers = parser.add_subparsers(title='Commands')
    parser_export = subparsers.add_parser('export', help='export database using a template')
    parser_export.add_argument('--template', help='template file')
    parser_export.add_argument('--docs', help='documents root path')
    parser_export.add_argument('output', help='output file')
    parser_export.set_defaults(func=export)
    parser_check = subparsers.add_parser('check', help='check database consistency')

    args = parser.parse_args()
    if args.database:
        args.db = Database(args.database)
    else:
        args.db = config.getDefaultDatabase()
    args.func(args)

if __name__ == '__main__':
    script()
