#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014-2015 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

from __future__ import division, print_function, unicode_literals
import concurrent.futures
import sys
import traceback
from contextlib import contextmanager


# we support PyQt5, PyQt4 and PySide - this import hell allows the rest of the module to be
# (almost) binding-agnostic
nullString = None
try:
    from PyQt5 import QtWidgets, QtCore
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon
    QT5 = True
except ImportError:
    QT5 = False
    try:
        from PyQt4 import QtGui, QtCore
        from PyQt4.QtCore import Qt
        from PyQt4.QtGui import QIcon
        QtWidgets = QtGui
        nullString = QtCore.QString()
    except ImportError:
        from PySide import QtGui, QtCore
        from PySide.QtCore import Qt
        from PySide.QtGui import QIcon
        QtWidgets = QtGui

from bibtexvcs.vcs import MergeConflict, AuthError, VCSNotFoundError, VCSInterface
from bibtexvcs.database import Database, Journal, JournalsFile, DatabaseFormatError
from pkg_resources import resource_filename


def standardIcon(widget, standardPixmap):
    """Helper function to generate a QIcon from a standardPixmap."""
    return widget.style().standardIcon(getattr(widget.style(), standardPixmap))


def jabrefIcon():
    """Return the JabRef icon which is bundled in the bibtexvcs package."""
    pngPath = resource_filename(__name__, 'JabRef-icon-32.png')
    return QIcon(pngPath)


class BtVCSGui(QtWidgets.QWidget):
    """Main window of the BibTeX VCS GUI application.

    Parameters
    ----------
    database : :class:`.Database` or str, optional
        Optional database to initialize the GUI with. If left out, opens the default database (if
        such exists) or starts without an open database otherwise.
    """

    def __init__(self, database=None):
        super(BtVCSGui, self).__init__()
        self.setWindowTitle('BibTeX VCS')
        self.guiIsComplete = False

        self._initGUI()
        self._initFutures()

        self._database = None
        self.show()
        if isinstance(database, Database):
            self.setDatabase(database)
        elif database is None:
            self._runAsync('Loading default database ...',
                          self.loadDatabase,
                          Database.getDefault)
        else:
            self._runAsync('Loading database ...',
                           self.loadDatabase,
                           Database,
                           database)

    def _initGUI(self):
        """Initializes GUI components before opening any database.

        After execution of this method, the GUI is in "reduced" state, showing only controls for
        cloning/opening a database. The full controls will be generated as soon as a database is
        loaded.
        """
        assert not self.guiIsComplete
        self.dbLabel = QtWidgets.QLabel('Please open or clone a BibTeX VCS database')
        dbSelectionButton = QtWidgets.QPushButton(standardIcon(self, 'SP_DialogOpenButton'), '&Open')
        dbSelectionButton.setToolTip('Open existing local checkout of a BibTeX VCS database')
        dbSelectionButton.clicked.connect(self.showOpenDatabaseDialog)
        dbCloneButton = QtWidgets.QPushButton(standardIcon(self, 'SP_DriveNetIcon'), '&Clone')
        dbCloneButton.setToolTip('Clone a BibTeX VCS database from a remote repository')
        dbCloneButton.clicked.connect(self.cloneDialog)

        dbLayout = QtWidgets.QHBoxLayout()
        dbLayout.addWidget(self.dbLabel)
        dbLayout.addStretch()
        dbLayout.addWidget(dbSelectionButton)
        dbLayout.addWidget(dbCloneButton)

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addLayout(dbLayout)
        self.publicLinkLabel = QtWidgets.QLabel('')
        self.publicLinkLabel.setOpenExternalLinks(True)
        mainLayout.addWidget(self.publicLinkLabel)
        self.setLayout(mainLayout)
        self.guiIsComplete = False

    def _ensureGUIIsComplete(self):
        if self.guiIsComplete:
            return
        buttonLayout = QtWidgets.QHBoxLayout()
        self.updateButton = QtWidgets.QPushButton(standardIcon(self, 'SP_ArrowDown'),
                                                  '&1: Update')
        self.updateButton.clicked.connect(self.updateRepository)
        jabrefButton = QtWidgets.QPushButton(jabrefIcon(), '&2: JabRef')
        jabrefButton.clicked.connect(self.jabref)
        self.commitButton = QtWidgets.QPushButton(standardIcon(self, 'SP_ArrowUp'),
                                                  '&3: Commit')
        self.commitButton.clicked.connect(self.runChecks)
        for button in self.updateButton, jabrefButton, self.commitButton:
            buttonLayout.addWidget(button)
        self.journalsTable = JournalsWidget(self._database)
        journalExpandButton = QtWidgets.QPushButton(standardIcon(self, 'SP_ToolBarVerticalExtensionButton'),
                                                    'Show Journals ...')
        journalExpandButton.setCheckable(True)
        self.layout().addWidget(journalExpandButton)
        journalExpandButton.toggled.connect(self.journalsTable.setVisible)
        self.layout().addWidget(self.journalsTable)
        self.journalsTable.hide()
        self.layout().addLayout(buttonLayout)
        self.guiIsComplete = True

    def _initFutures(self):
        """Initializes helpers for asynchronous function calls (see :func:`runAsync`).
        """
        self.futureExecutor = concurrent.futures.ThreadPoolExecutor(1)
        self.futureTimer = QtCore.QTimer(self)
        self.futureTimer.setInterval(20)
        self.futureTimer.timeout.connect(self._updateFuture)
        self.progressDialog = QtWidgets.QProgressDialog(self)
        self.progressDialog.setRange(0, 0)
        self.progressDialog.setCancelButtonText(nullString)
        self.progressDialog.setWindowModality(Qt.WindowModal)

    def loadDatabase(self):
        """Loads the database that was instanciated asynchronously and is available in
        :attr:`future`.
        """
        with self.catchExceptions():
            database = self.future.result()
            if database:
                self.setDatabase(database)

    def setDatabase(self, database):
        """Set the current database to `database`.

        On the first time this method is called after window creation, the GUI is completed with the
        controls for journal management etc.
        """
        self._database = database
        self._ensureGUIIsComplete()
        self.reload()
        self.updateRepository()

    def reload(self):
        """Reload GUI components after the database has been changed or updated.

        Resets database controls, journals table, window title, etc.
        """
        self.journalsTable.setDB(self._database)
        if self._database.publicLink:
            self.publicLinkLabel.setText('Web: <a href="{0}">{0}</a>'.format(self._database.publicLink))
        self.publicLinkLabel.setVisible(self._database.publicLink is not None)
        if self._database.vcs is not None:
            self.dbLabel.setText('Database: <i>{}</i><br />r. {}, changed {}'
                                 .format(self._database.directory, *self._database.vcs.revision()))
            self.updateButton.setEnabled(True)
            self.commitButton.setEnabled(True)
        else:
            self.dbLabel.setText('Database: <i>{}</i><br />Not under version control.'
                                 .format(self._database.directory))
            self.updateButton.setEnabled(False)
            self.commitButton.setEnabled(False)
        self.setWindowTitle("BibTeX VCS: {}".format(self._database.name))

    def _runAsync(self, labelText, finishedCall, fn, *args, **kwargs):
        """Helper function for asynchronous calls during which a progress dialog labelled
        `labelText` is shown.

        Parameters
        ----------
        finishedCall : callable
            Function that will be called after `fn` has finished running. May be `None`.
        fn : callable
            The function to be run asynchronously. Additional positional and keyword arguments are
            passed to `fn`.
        """
        self.progressDialog.setLabelText(labelText)
        self.progressDialog.show()
        self.finishedCall = finishedCall
        self.future = self.futureExecutor.submit(fn, *args, **kwargs)
        self.futureTimer.start()

    def _updateFuture(self):
        if self.future.done():
            self.futureTimer.stop()
            self.progressDialog.close()
            if self.finishedCall:
                self.finishedCall()

    @contextmanager
    def catchExceptions(self, onAuthEntered=None):
        """Contextmanager catching common exceptions and displaying message boxes if they occur.

        The caught exceptions are :class:`DatabaseFormatError`, :class:`MergeConflict` and
        :class:`AuthError`.

        `onAuthEntered` is an optional callable. If it is provided and an :class:`AuthError` is
        caught, the following happens:

        - A :class:`LoginDialog` is shown to ask the user for a login,
        - if the dialog is canceled, the :class:`AuthError` is re-raised
        - otherwise, the function `onAuthEntered` is called.

        If the `store login` checkbox in the :class:`LoginDialog` was checked, the information is
        set to `self.db.vcs` and :fun:`config.setAuthInformation` is called.
        """
        M = QtWidgets.QMessageBox
        try:
            yield
        except DatabaseFormatError as e:
            M.critical(self, 'Error Opening Database', str(e))
        except MergeConflict as mc:
            M.critical(self, "Merge conflict", str(mc))
        except AuthError as a:
            if onAuthEntered is not None:
                ans = LoginDialog.getLogin(self, str(a))
                if ans is not None:
                    self._database.vcs.setLogin(ans['login'])
                    store = ans['storeLogin']
                    if store:
                        self._database.vcs.storeLogin()
                    onAuthEntered()
                    return
            M.critical(self, "Authorization Required", str(a))
        except VCSNotFoundError as e:
            M.critical(self, 'VCS program not found', str(e))
        except Exception as e:
            M.critical(self, 'Unhandled {}'.format(type(e)), traceback.format_exc())

    def showOpenDatabaseDialog(self):
        """Opens a dialog to select a database from a local directory, and then loads that database.
        """
        ans = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Database Directory')
        if ans:
            with self.catchExceptions():
                database = Database(ans)
                self.setDatabase(database)

    def cloneDialog(self):
        """Opens a dialog to select a source for cloning a database, and then loads that database.
        """
        cloneDialog = CloneDialog(self)
        if cloneDialog.exec_() == cloneDialog.Accepted:
            self._cloneDB_init(cloneDialog.url(), cloneDialog.target(), cloneDialog.vcsType(),
                               cloneDialog.login())

    def _cloneDB_init(self, url, target, vcsType, *args, **kwargs):
        """Initialize asynchronous cloning of a (remote) database.
        """
        self._cloneURL = url
        self._cloneTarget = target
        self._cloneVCS = vcsType
        self._runAsync('Cloning database ... ', self._cloneDB_handle,
                       VCSInterface.getClonedDatabase, url, target, vcsType, *args, **kwargs)

    def _cloneDB_handle(self):
        with self.catchExceptions():
            try:
                self.setDatabase(self.future.result())
            except AuthError as e:
                ans = LoginDialog.getLogin(self, str(e))
                if ans:
                    login, storeLogin = ans
                    self._cloneDB_init(self._cloneURL, self._cloneTarget, self._cloneVCS,
                                       login, storeLogin=storeLogin)
                else:
                    raise e

    def updateRepository(self):
        self._runAsync("Updating repository ...", self.update_handle, self._database.vcs.update)

    def update_handle(self):
        with self.catchExceptions(onAuthEntered=self.updateRepository):
            changed = self.future.result()
            if changed:
                QtWidgets.QMessageBox.information(self,
                        "Update successful", "Successfully merged remote changes")
                self.reload()

    def jabref(self):
        try:
            self._database.runJabref()
        except FileNotFoundError as e:
            QtWidgets.QMessageBox.critical(self, 'Could not start JabRef', str(e))

    def runChecks(self):
        self._runAsync("Performing database checks ...", self.runChecks_handle, self.runChecks_init)

    def runChecks_init(self):
        from bibtexvcs import checks
        self._database.reload()
        return checks.performDatabaseCheck(self._database)

    def runChecks_handle(self):
        self.reload()
        errors, warnings = self.future.result()
        if len(errors) > 0:
            title = "Database Check Failed"
            text = 'One or more database checks failed. Please fix, then try again.'
            detailed = "\n\n".join(err.args[0] for err in errors)
            box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, title, text, parent=self)
            box.setDetailedText(detailed)
            box.setStandardButtons(box.Close)
            box.exec_()
        elif len(warnings) > 0:
            box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, 'Warning',
                    'All checks passed, but some warnings occured. Proceed anyway?', parent=self)
            box.setDetailedText("\n\n".join(war.args[0] for war in warnings))
            box.setStandardButtons(box.Yes | box.No)
            if box.exec_() == box.Yes:
                self.commit_init()
        else:
            self.commit_init()

    def commit_init(self):
        self._runAsync("Committing repository ...", self.commit_handle, self._database.vcs.commit)

    def commit_handle(self):
        with self.catchExceptions(onAuthEntered=self.commit_init):
            if not self.future.result():
                QtWidgets.QMessageBox.information(self, "No Local Changes", "Nothing to commit.")
            else:
                QtWidgets.QMessageBox.information(self, "Commit successful", "Commit successful.")
                self.reload()

    def closeEvent(self, event):
        if self._database and self._database.vcs and self._database.vcs.hasLocalChanges():
            ans = QtWidgets.QMessageBox.question(self, "Local changes present",
                    "Database was modified locally. Are you sure you want to quit "
                    "without committing the changes?",
                    QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes)
            if ans == QtWidgets.QMessageBox.Yes:
                self._database.setDefault()
                event.accept()
            else:
                event.ignore()
        else:
            if self._database:
                self._database.setDefault()
            event.accept()


class JournalsWidget(QtWidgets.QWidget):
    """Widget for displaying the journal abbreviations, including buttons to add/remove entries."""
    def __init__(self, db):
        super(JournalsWidget, self).__init__()
        self.table = QtWidgets.QTableWidget(len(db.journals), 3)
        self.table.setHorizontalHeaderLabels(['Macro', 'Abbreviated', 'Full'])
        self.setDB(db)
        fName = 'setSectionResizeMode' if QT5 else 'setResizeMode'
        getattr(self.table.horizontalHeader(), fName)(2, QtWidgets.QHeaderView.ResizeToContents)
        for i in range(1,3):
            getattr(self.table.horizontalHeader(), fName)(i, QtWidgets.QHeaderView.Interactive)

        getattr(self.table.verticalHeader(), fName)(QtWidgets.QHeaderView.ResizeToContents)
        layout = QtWidgets.QVBoxLayout()
        journalsLabel = QtWidgets.QLabel('Search:')
        self.searchEdit = QtWidgets.QLineEdit()
        self.searchEdit.textChanged.connect(self.search)
        newJournalButton = QtWidgets.QPushButton(QIcon.fromTheme('list-add'), '&Add Journal')
        delJournalButton = QtWidgets.QPushButton(standardIcon(self, 'SP_TrashIcon'), '&Delete')
        delJournalButton.clicked.connect(self.deleteCurrent)
        newJournalButton.clicked.connect(self.addJournal)
        explLabel = QtWidgets.QLabel('For easy switching between full and abbreviated journal names'
                                     ' in your documents, you should introduce journal macros for '
                                     'every journal used instead of hard-coding the journal name '
                                     'into the bib file. Use the table below to manage those macros'
                                     '. Add either <code>{}</code> or <code>{}</code> as bibliography '
                                     'resource to have the corresponding style in jour TeX doc.'
                                     .format(self.db.abbrJournalsName,
                                             self.db.fullJournalsName))
        explLabel.setWordWrap(True)
        explLabel.setTextFormat(Qt.RichText)
        layout.addWidget(explLabel)

        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addWidget(journalsLabel)
        buttonLayout.addWidget(self.searchEdit)
        buttonLayout.addStretch()
        buttonLayout.addWidget(newJournalButton)
        buttonLayout.addWidget(delJournalButton)
        layout.addLayout(buttonLayout)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.table.cellChanged.connect(self.updateJournalsFile)
        self.dontUpdate = False
        layout.setContentsMargins(0, 0, 0, 0)

    def search(self, text):
        for row in range(self.table.rowCount()):
            hide = True
            for col in range(self.table.columnCount()):
                if text in self.table.item(row, col).text():
                    hide = False
                    break
            self.table.setRowHidden(row, hide)

    @staticmethod
    def makeItem(text, editable=True):
        item = QtWidgets.QTableWidgetItem(text)
        if not editable:
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item

    def setDB(self, db):
        self.db = db
        self.dontUpdate = True
        self.table.clearContents()
        self.table.setRowCount(len(self.db.journals))
        for i, journal in enumerate(self.db.journals.values()):
            self.table.setItem(i, 0, self.makeItem(journal.macro, False))
            self.table.setItem(i, 1, self.makeItem(journal.abbr))
            self.table.setItem(i, 2, self.makeItem(journal.full))
        self.dontUpdate = False
        self.table.horizontalHeader().resizeSections(QtWidgets.QHeaderView.ResizeToContents)

    def deleteCurrent(self):
        currentRow = self.table.currentRow()
        self.table.removeRow(currentRow)
        self.updateJournalsFile()

    def addJournal(self):
        macro, ok = QtWidgets.QInputDialog.getText(self.parent(), "New Journal's Macro",
                'Please enter the <i>Macro</i> of the new journal')
        if not ok:
            return
        for i in range(self.table.rowCount()):
            if self.table.item(i, 2).text() == macro:
                QtWidgets.QMessageBox.critcical(self.parent(), 'Macro exists',
                        "The macro '{}' is already in use by another journal".format(macro))
                return
        index = self.table.rowCount()
        self.dontUpdate = True
        self.table.insertRow(index)
        self.table.setItem(index, 2, self.makeItem(macro))
        # initialize abbr and full with the macro
        self.table.setItem(index, 0, self.makeItem(macro, False))
        self.dontUpdate = False
        self.table.setItem(index, 1, self.makeItem(macro))
        self.table.selectRow(index)

    def updateJournalsFile(self):
        if self.dontUpdate:
            return
        journals = []
        for i in range(self.table.rowCount()):
            macro, abbr, full = [self.table.item(i, j).text() for j in (0, 1, 2)]
            if sys.version_info.major == 2 and not isinstance(full, unicode):
                full, abbr, macro = [unicode(s) for s in (full, abbr, macro)]
            journals.append(Journal(full=full, abbr=abbr, macro=macro))
        self.db.journals = JournalsFile(journals=journals)
        self.db.journals.write(self.db.journalsPath)
        self.db.makeJournalBibfiles()


class CloneDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(CloneDialog, self).__init__(parent)
        layout = QtWidgets.QGridLayout()
        self.urlEdit = QtWidgets.QLineEdit()
        self.urlEdit.setPlaceholderText("remote repository URL")
        layout.addWidget(QtWidgets.QLabel("URL:"), 0, 0)
        layout.addWidget(self.urlEdit, 0, 1)
        self.vcsTypeChooser = QtWidgets.QComboBox()
        self.vcsTypeChooser.addItems(VCSInterface.vcsTypeNames())
        layout.addWidget(self.vcsTypeChooser, 0, 2)
        layout.addWidget(QtWidgets.QLabel('Target:'), 1, 0)
        self.targetEdit = QtWidgets.QLineEdit()
        self.targetEdit.setPlaceholderText('local checkout directory')
        layout.addWidget(self.targetEdit, 1, 1)
        chooseTargetButton = QtWidgets.QPushButton('Choose...')
        chooseTargetButton.clicked.connect(lambda: self.targetEdit.setText(
                QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose Target')))
        layout.addWidget(chooseTargetButton, 1, 2)
        Ok = QtWidgets.QDialogButtonBox.Ok
        Cancel = QtWidgets.QDialogButtonBox.Cancel
        self.btbx = QtWidgets.QDialogButtonBox(Cancel | Ok)
        self.btbx.button(Ok).setEnabled(False)
        layout.addWidget(self.btbx, 2, 0, 1, 3)
        layout.setColumnMinimumWidth(1, 250)
        self.btbx.rejected.connect(self.reject)
        self.btbx.accepted.connect(self.accept)
        self.targetEdit.textChanged.connect(self.checkOk)
        self.urlEdit.textChanged.connect(self.checkOk)
        self.setLayout(layout)

    def checkOk(self):
        ok = all((edit.text().strip() != '' for edit in (self.targetEdit, self.urlEdit)))
        self.btbx.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(ok)


class LoginDialog(QtWidgets.QDialog):

    def __init__(self, message=None, parent=None):
        super(LoginDialog, self).__init__(parent)

        layout = QtWidgets.QGridLayout()
        if message:
            layout.addWidget(QtWidgets.QLabel(message), 0, 0, 1, 2)
        layout.addWidget(QtWidgets.QLabel('User:'), 1, 0)
        layout.addWidget(QtWidgets.QLabel('Password:'), 2, 0)
        self.userEdit = QtWidgets.QLineEdit()
        self.userEdit.setPlaceholderText('enter username')
        layout.addWidget(self.userEdit, 1, 1)
        self.passEdit = QtWidgets.QLineEdit()
        self.passEdit.setPlaceholderText('enter password')
        self.passEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(self.passEdit, 2, 1)
        self.storeBox = QtWidgets.QCheckBox('Remember login')
        layout.addWidget(self.storeBox, 3, 1)
        btbx = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel |
                                          QtWidgets.QDialogButtonBox.Ok)
        btbx.accepted.connect(self.accept)
        btbx.rejected.connect(self.reject)
        layout.addWidget(btbx, 4, 0, 1, 2)
        self.setLayout(layout)

    @staticmethod
    def getLogin(parent=None, message=None):
        dialog = LoginDialog(parent=parent, message=message)
        if dialog.exec_() == dialog.Accepted:
            return dict(username=dialog.userEdit.text(),
                        password=dialog.passEdit.text(),
                        storeLogin=dialog.storeBox.isChecked())
        return None


def run(database=None):
    import bibtexvcs, pkg_resources
    from distutils.version import StrictVersion
    app = QtWidgets.QApplication(sys.argv)
    window = None
    newVersion = bibtexvcs.pypiVersion()
    if newVersion:
        newVersion = StrictVersion(newVersion)
        myVersion = StrictVersion(pkg_resources.get_distribution('bibtexvcs').version)
        if newVersion > myVersion:
            window = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical,
                                           "New version available",
                                           "A new version of BibTeX VCS ({}) is available. "
                                           "Please update (pip install -U --user bibtexvcs), "
                                           "then start again.".format(newVersion),
                                           QtWidgets.QMessageBox.Ok)
            window.show()
            window.accepted.connect(app.exit)
    if window is None:
        window = BtVCSGui(database)
    app.exec_()

if __name__ == '__main__':
    run()
