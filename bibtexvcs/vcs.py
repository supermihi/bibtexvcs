#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

class VCSInterface:
    
    def __init__(self, root):
        self.root = root
        

class MercurialInterface(VCSInterface):
    
    def localChanges(self):