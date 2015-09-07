#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import os, subprocess, sys

from bibtexvcs import config


class Login:
    """Data class representing login information for a remote repository.
    """
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password


class MergeConflict(Exception):
    """Raised when merge conflicts occur on a VCS update operation."""
    pass


class AuthError(Exception):
    """Raised on authentication errors when accessing remote repositories."""
    pass


class VCSNotFoundError(Exception):
    """Raised when the necessary VCS binary (e.g. "hg") is not installed."""


class VCSInterface:
    """Interface to the version control system (VCS) of a :mod:`bibtexvcs` database.
    """

    __typeMap = {}

    def __init__(self, database):
        self.database = database
        storedLogin = Login(*config.getLogin(database))
        self.login = storedLogin

    @property
    def root(self):
        """Returns the root directory of this repository.
        """
        return self.database.directory

    def storeLogin(self, login):
        """Permanently store login information for this repository.
        """
        config.storeLogin(self.database, self.login.username, self.login.password)

    def add(self, path):
        """Adds a file or directory to the repository.
        """

    def hasLocalChanges(self):
        """Determines whether any local changes have been made to the repository.
        Returns
        -------
        bool
            Return value is ``True`` iff one of the following requirements are met:

            - any versioned file has been modified,
            - any versioned file in the documents folder has been deleted, or
            - any unversioned file has been placed in the documents folder.
        """
        raise NotImplementedError()

    def update(self):
        """Checks if there are updates in the remote repository. If so, tries to merge
        them and reloads the database.

        Returns
        -------
        bool
            Flag indicating if something was updated or not.
        Raises
        ------
        MergeConflict
            If update results in a merge that cannot be handled automatically.
        """
        raise NotImplementedError()

    def commit(self, commitMessage=None):
        """Commit local changes and push to remote, if remote is configured.

        Returns
        ----------
        bool
            Indicator being ``True`` iff there actually were any changes.
        """
        raise NotImplementedError()

    def revision(self):
        """Returns a tuple containing the current revision and its date."""
        raise NotImplementedError()


    @staticmethod
    def vcsTypeNames():
        """Returns the names of all registered VCS types."""
        return VCSInterface.__typeMap.keys()

    @staticmethod
    def registerVCSType(vcsTypeName, vcsTypeClass):
        """Register a new VCS type."""
        VCSInterface.__typeMap[vcsTypeName] = vcsTypeClass

    @staticmethod
    def getImplementation(vcsTypeName):
        if vcsTypeName == 'local':
            return None
        try:
            return VCSInterface.__typeMap[vcsTypeName]
        except KeyError:
            raise KeyError('No VCS implementation of type "{}" available'.format(vcsTypeName))

    @staticmethod
    def get(database):
        return VCSInterface.getImplementation(database.vcsType)(database)

    @classmethod
    def clone(cls, url, target, login=None):
        """Clones a remote repository.

        Parameters
        ----------
        url : str
            The remote repository URL.
        target : str
            The local target directory.
        login : Login
            Login information.
        """
        raise NotImplementedError()

    @staticmethod
    def getClonedDatabase(url, target, vcsType, login=None, storeLogin=False):
        """Clone and return a database from a remote location specified by `url`.

        Parameters
        ----------
        url : str
            Source URL of the repository.
        target : str
            Local target directory.
        vcsType
            VCS system to use.
        login : Login
            Login information (optional).
        storeLogin : bool (optional)
            Store login on successful authentication.
        """
        vcsCls = VCSInterface.getImplementation(vcsType)
        if login is None:
            login = Login()
        vcsCls.clone(url, target, login)
        from bibtexvcs.database import Database
        database = Database(target)
        # copy login information
        database.vcs.login = login
        if storeLogin:
            database.vcs.storeLogin()
        return database


class MercurialInterface(VCSInterface):
    """Interface to the `Mercurial <http://mercurial.selenic.com>`_ version control system.
    """

    cmdline = ['hg', '--noninteractive', '--config', 'auth.x.prefix=*']

    def __init__(self, *args, **kwargs):
        super(MercurialInterface, self).__init__(*args, **kwargs)
        try:
            self.hasRemote = len(self.callHg('showconfig', 'paths.default')) > 0
        except subprocess.CalledProcessError:
            # some hg versions appear to return exit status 1 if req'ed config noit set
            self.hasRemote = False
        self.hgid = self.callHg('id', '-i')

    def callHg(self, *args):
        """Calls the ``hg`` script in the database directory with the given arguments.
        """
        return MercurialInterface._callHg(*args, login=self.login, cwd=self.root)

    @classmethod
    def _callHg(cls, *args, **kwargs):
        cmdline = cls.cmdline[:]
        kwargs = kwargs.copy()
        if kwargs.get('login'):
            login = kwargs['login']
            if login.username:
                cmdline += ['--config', 'auth.x.username={}'.format(login.username)]
            if login.password:
                cmdline += ['--config', 'auth.x.password={}'.format(login.password)]
        if 'login' in kwargs:
            del kwargs['login']
        env = os.environ.copy()
        env['LANG'] = 'C'
        env['LANGUAGE'] = 'C'  # on Ubuntu 12.04, LANG=C does not convince hg to use english output
        try:
            return subprocess.check_output(cmdline + list(args), env=env,
                                           stderr=subprocess.STDOUT, **kwargs)
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors='replace')
            if "authorization required" in output:
                raise AuthError('Authorization required for the mercurial repository.')
            if "authorization failed" in output:
                raise AuthError('Authorization for the mercurial repository failed.')
            if 'conflicts during merge' in output:
                raise MergeConflict('Conflict arised when merging remote and local changes!\n'
                                    'You need to fix this issue by hand. Error message:\n{}'
                                    .format(e.output))
            if 'unresolved merge conflicts' in output:
                raise MergeConflict('There are unresolved merge conflicts in your repository.\n'
                                    'You have to fix them manually before proceeding to use this '
                                    'tool.')
            print(output)
            raise e
        except OSError as e:
            raise VCSNotFoundError('Could not run "hg". Please install mercurial')

    def add(self, path):
        self.callHg('add', path)

    def hasLocalChanges(self):
        if len(self.callHg('status', '--modified', '--added')) > 0:
            return True
        # by this we ignore unversioned files in the base folder
        return len(self.callHg('status', '--deleted', '--unknown', self.database.documents)) > 0

    def update(self):
        if self.hasRemote:
            self.callHg('pull')
        # force internal merge algorithm with "-t merge" to prevent GUI tools opening
        self.callHg('update', '-t', ':merge')
        newId = self.callHg('id', '-i')
        if newId != self.hgid:
            self.hgid = newId
            self.database.reload()
            return True
        return False

    def commit(self, commitMessage=None):
        if not self.hasLocalChanges():
            return False
        hgOutput = self.callHg('status', '--deleted', '--no-status', self.database.documents)
        deletedDocs = hgOutput.decode(sys.getfilesystemencoding()).splitlines()
        if len(deletedDocs) > 0:
            self.callHg('remove', *deletedDocs)
        hgOutput = self.callHg('status', '--unknown', '--no-status', self.database.documents)
        newDocs = hgOutput.decode().splitlines()
        if len(newDocs) > 0:
            self.callHg('add', *newDocs)
        # TODO: sophisticated analysis of diff to current head
        self.callHg('commit', '--message', commitMessage or 'Auto-Commit by BibTeX VCS')
        if self.hasRemote:
            self.callHg('push')
        self.database.reload()
        self.hgid = self.callHg('id', '-i')
        return True

    def revision(self):
        return self.callHg('log', '-l', '1', '--template', '{rev}\n{date|isodate}'
                           ).decode().splitlines()

    @classmethod
    def clone(cls, url, target, login=None):
        if login is None:
            login = Login()
        cls._callHg('clone', url, target, login=login)


VCSInterface.registerVCSType('mercurial', MercurialInterface)