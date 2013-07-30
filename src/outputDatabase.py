#!/usr/bin/python

import sys

import jinja2

from literature.database import LiteratureDatabase
from literature import journals

dtb = LiteratureDatabase(sys.argv[1])
journals = journals.readJournalFile(sys.argv[2])
for key, item in dtb.entries.items():
    try:
        print(item.authorLastNames(3), item["journal"] if "journal" in item else "")
    except KeyError:
        print(key)