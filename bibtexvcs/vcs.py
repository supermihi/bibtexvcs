#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import subprocess

class MergeConflict(Exception):
    pass

class AuthRequired(Exception):
    pass

typeMap = {}

class VCSMeta(type):
    def __init__(cls, name, base, namespace):
        super().__init__(name, base, namespace)
        if hasattr(cls, 'vcsType'):
            typeMap[cls.vcsType] = cls

    
class VCSInterface(metaclass=VCSMeta):
    """Interface to the version control system (VCS) of a :mod:`bibtexvcs` database.
    """
    def __init__(self, db):
        self.db = db
        self.root = db.directory
    
    def add(self, path):
        """Adds a file or directory to the repository.
        
        :param path: The path (relative to the vcs root).
        :type path: str
        """
    
    def localChanges(self):
        """Determines whether any local changes have been made to the repository.
        
        Returns ``True`` if one of the following requirements are met:
        
        - any versioned file has been modified,
        - any versioned file in the documents folder has been deleted, or
        - any unversioned file has been placed in the documents folder.
        """
        raise NotImplementedError()
    
    def update(self):
        """Checks if there are updates in the remote repository. If so, tries to merge
        them and reloads the database.
        
        :return: ``True`` if something was update, ``False`` otherwise. 
        :raises: :class:`MergeConflict` if a conflict is introduced by merging."""
        raise NotImplementedError()
    
    def commit(self, msg=None):
        """Commit local changes and push to remote, if exists.
        
        :param msg: Commit message.
        :type msg:  str"""
        raise NotImplementedError()
    
    @staticmethod
    def get(db):
        try:
            return typeMap[db.vcsType](db)
        except KeyError:
            raise KeyError("No VCS type '{}' is known".format(db.vcsType))

    @classmethod
    def clone(cls, url, target):
        """Clones the repsoitory at ``url`` into the directory ``target``."""
        raise NotImplementedError()

    
class MercurialInterface(VCSInterface):
    
    vcsType = 'mercurial'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hasRemote = len(self.callHg("showconfig", "paths.default")) > 0
    
    def callHg(self, *args, **kwargs):
        """Calls the hg script in the repo directory with given args.
        Any keyword arguments are passed to the subprocess.check_output function call.
        """
        try:
            return subprocess.check_output(["hg", "--noninteractive"] + list(args), 
                                           env={'LANG': 'C'}, cwd=self.root,
                                           stderr=subprocess.STDOUT, **kwargs)
        except subprocess.CalledProcessError as e:
            output = e.output.decode()
            if "authorization required" in output:
                raise AuthRequired('Authorization required for the mercurial repository. '
                                   'Please add auth information to your hgrc file.')
            if 'conflicts during merge' in output:
                raise MergeConflict('Conflict arised when merging remote and local changes!\n'
                                    'You need to fix this issue by hand. Error message:\n{}'
                                    .format(e.output))
            if 'unresolved merge conflicts' in output:
                raise MergeConflict('There are unresolved merge conflicts in your repository.\n'
                                    'You have to fix them manually before proceeding to use this '
                                    'tool.')
            raise e
    
    def add(self, path):
        self.callHg('add', path)
    
    def localChanges(self):
        if len(self.callHg('status', '--modified', '--added')) > 0:
            return True
        # by this we ignore unversioned files in the base folder
        return len(self.callHg('status', '--deleted', '--unknown', self.db.documents)) > 0
    
    def update(self):
        if self.hasRemote:
            cmd = ['pull', '--update']
        else:
            cmd = ['update']
        ans = self.callHg(*cmd).decode()
        if 'no changes found' in ans:
            return False
        self.db.reload()
        return True
        
    def commit(self, msg=None):
        if not self.localChanges():
            return False
        self.update() # merge potential remote changes before commiting
        hgOutput = self.callHg('status', '--deleted', '--no-status', self.db.documents)
        deletedDocs = hgOutput.decode().splitlines()
        if len(deletedDocs) > 0:
            self.callHg('remove', *deletedDocs)
        hgOutput = self.callHg('status', '--unknown', '--no-status', self.db.documents)
        newDocs = hgOutput.decode().splitlines()
        if len(newDocs) > 0:
            self.callHg('add', *newDocs)
        #TODO: sophisticated analysis of diff to current head
        self.callHg('commit', '--message', msg or 'Auto-Commit by BibTeX VCS')
        if self.hasRemote:
            self.callHg('push')
        return True

    @classmethod
    def clone(cls, url, target):
        subprocess.check_call(['hg', 'clone', url, target])

class NoVCSInterface(VCSInterface):
    
    vcsType = None
    
    """Dummy VCS interface for the case of a database that is not under version control."""

    def __getattribute__(self, name):
        if name in ("add", "localChanges", "update", "commit"):
            return lambda *args, **kwargs: False
        return super().__getattribute__(name)
