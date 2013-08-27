#!/usr/bin/python

import sys

import jinja2

from literature.database import LiteratureDatabase
from literature import journals

dtb = LiteratureDatabase(sys.argv[1], sys.argv[2])
env = jinja2.Environment(loader=jinja2.FileSystemLoader("."), autoescape=True)
template = env.get_template('example.html')
print(template.render(entries=dtb.entries.values()))
