#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2014 Michael Helmling
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation

import subprocess
import os.path
from contextlib import contextmanager

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from bibtexvcs.vcs import MergeConflict, typeMap, AuthRequired
from bibtexvcs.database import Database, Journal, JournalsFile, DatabaseFormatError, BTVCSCONF
from bibtexvcs import config

def standardIcon(widget, standardPixmap):
    return widget.style().standardIcon(getattr(widget.style(), standardPixmap))

class JournalsWidget(QtWidgets.QWidget):
    
    def __init__(self, db):
        super().__init__()
        self.table = QtWidgets.QTableWidget(len(db.journals), 3)
        self.table.setHorizontalHeaderLabels([self.tr("Full"), self.tr("Abbreviated"), self.tr("Macro")])
        self.setDB(db)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSizeAdjustPolicy(self.table.AdjustToContents)
        
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.table)
        
        newJournalButton = QtWidgets.QPushButton(self.tr("Add Journal"))
        delJournalButton = QtWidgets.QPushButton(standardIcon(self, "SP_TrashIcon"),
                                                 self.tr("Delete"))
        delJournalButton.clicked.connect(self.deleteCurrent)
        newJournalButton.clicked.connect(self.addJournal)
        
        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(newJournalButton)
        buttonLayout.addWidget(delJournalButton)
        layout.addLayout(buttonLayout)
        self.setLayout(layout)
        self.table.cellChanged.connect(self.updateJournalsFile)
        self.dontUpdate = False
    
    def makeItem(self, text, editable=True):
        item = QtWidgets.QTableWidgetItem(text)
        if not editable:
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item
    
    def setDB(self, db):
        self.db = db
        self.dontUpdate = True
        self.table.clearContents()
        for i, journal in enumerate(self.db.journals.values()):
            self.table.setItem(i, 0, self.makeItem(journal.full))
            self.table.setItem(i, 1, self.makeItem(journal.abbr))
            self.table.setItem(i, 2, self.makeItem(journal.macro, False))
        self.dontUpdate = False
        
    def deleteCurrent(self):
        currentRow = self.table.currentRow()
        self.table.removeRow(currentRow)
        self.updateJournalsFile()
        
    def addJournal(self):
        macro, ok = QtWidgets.QInputDialog.getText(self.parent(),
            self.tr("New Journal's Macro"),
            self.tr("Please enter the <i>Macro</i> of the new journal"))
        if not ok:
            return
        for i in range(self.table.rowCount()):
            if self.table.item(i, 2).text() == macro:
                QtWidgets.QMessageBox.critcical(self.parent(), self.tr("Macro exists"), 
                    self.tr("The macro '{}' is already chosen by another journal.").format(macro))
                return
        index = self.table.rowCount()
        self.dontUpdate = True
        self.table.insertRow(index)
        self.table.setItem(index, 2, self.makeItem(macro, False))
        # initialize abbr and full with the macro
        self.table.setItem(index, 0, self.makeItem(macro))
        self.dontUpdate = False
        self.table.setItem(index, 1, self.makeItem(macro))
        self.table.resizeRowsToContents()
        
    def updateJournalsFile(self):
        if self.dontUpdate:
            return
        journals = []
        for i in range(self.table.rowCount()):
            journals.append(Journal(full=self.table.item(i, 0).text(),
                                    abbr=self.table.item(i, 1).text(),
                                    macro=self.table.item(i, 2).text()))
        jFile = JournalsFile(journals=journals)
        jFile.write(self.db.journalsPath)
        
        
class CloneDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout()
        self.urlEdit = QtWidgets.QLineEdit()
        self.urlEdit.setPlaceholderText(self.tr("remote repository URL"))
        layout.addWidget(QtWidgets.QLabel(self.tr("URL:")), 0, 0)
        layout.addWidget(self.urlEdit, 0, 1)
        self.vcsTypeChooser = QtWidgets.QComboBox()
        self.vcsTypeChooser.addItems([t for t in typeMap if t is not None])
        layout.addWidget(self.vcsTypeChooser, 0, 2)
        layout.addWidget(QtWidgets.QLabel(self.tr("Target:")), 1, 0)
        self.targetEdit = QtWidgets.QLineEdit()
        self.targetEdit.setPlaceholderText(self.tr("local checkout directory"))
        layout.addWidget(self.targetEdit, 1, 1)
        chooseTargetButton = QtWidgets.QPushButton(self.tr("Choose..."))
        chooseTargetButton.clicked.connect(self.chooseTarget)
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
        self.setLayout(layout)
    
    def checkOk(self):
        ok = all((edit.text().strip() != '' for edit in (self.targetEdit, self.urlEdit)))
        self.btbx.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(ok)
    
    def chooseTarget(self):
        target = QtWidgets.QFileDialog.getExistingDirectory(self, self.tr("Choose Target"))
        if target:
            self.targetEdit.setText(target)
        

class BtVCSGui(QtWidgets.QWidget):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BibTeX VCS")
        
        layout = QtWidgets.QVBoxLayout()
        
        dbLayout = QtWidgets.QHBoxLayout()
        self.dbLabel = QtWidgets.QLabel(self.tr("Please open a database"))
        dbSelect = QtWidgets.QPushButton(standardIcon(self, "SP_DialogOpenButton"),
                                         self.tr("Open"))
        dbSelect.setToolTip(self.tr("Open existing local checkout of a BibTeX VCS database"))
        dbSelect.clicked.connect(self.openDialog)
        dbClone = QtWidgets.QPushButton(standardIcon(self, "SP_DriveNetIcon"),
                                        self.tr("Clone"))
        dbClone.setToolTip(self.tr("Clone a BibTeX VCS database from a remote repository"))
        dbClone.clicked.connect(self.cloneDialog)
        
        dbLayout.addWidget(self.dbLabel)
        dbLayout.addStretch()
        dbLayout.addWidget(dbSelect)
        dbLayout.addWidget(dbClone)
        layout.addLayout(dbLayout)
        
        self.guiComplete = False
        
        btbx = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btbx.rejected.connect(self.close)
        layout.addWidget(btbx)
        
        self.setLayout(layout)
        self.db = None
        self.show()
        
    def setDB(self, db):
        self.db = db
        if not self.guiComplete:
            index = self.layout().count() - 1 # insert everything before the btbx
            buttonLayout = QtWidgets.QHBoxLayout()
            
            updateButton = QtWidgets.QPushButton(standardIcon(self, "SP_ArrowDown"),
                                                 self.tr("Update Repository"))
            updateButton.clicked.connect(self.updateRepository)
            buttonLayout.addWidget(updateButton)
            
            openJabrefButton = QtWidgets.QPushButton(self.tr("Start JabRef"))
            openJabrefButton.clicked.connect(self.jabref)
            buttonLayout.addWidget(openJabrefButton)
            
            commitButton = QtWidgets.QPushButton(standardIcon(self, "SP_ArrowUp"),
                                                 self.tr("Commit Changes"))
            commitButton.clicked.connect(self.commit)
            buttonLayout.addWidget(commitButton)
            
            self.layout().insertLayout(index, buttonLayout)
            
            journalsLabel = QtWidgets.QLabel(self.tr("<h3>Journals Management</h3>"))
            self.layout().insertWidget(index+1, journalsLabel)
            self.journalsTable = JournalsWidget(self.db)
            self.layout().insertWidget(index+2, self.journalsTable)
            self.guiComplete = True
        else:
            self.journalsTable.setDB(db)
        self.dbLabel.setText(self.tr("Database location: {}").format(db.directory))
        self.setWindowTitle(self.tr("BibTeX VCS – {}").format(db.name))

    @contextmanager
    def catchExceptions(self):
        M = QtWidgets.QMessageBox
        try:
            yield
            return True
        except DatabaseFormatError as e:
            M.critical(self, self.tr('Error Opening Database'), str(e))
        except MergeConflict as mc:
            M.critical(self, self.tr("Merge conflict"), str(mc))
        except AuthRequired as a:
            M.critical(self, self.tr("Authorization Required"), str(a))
        
    def reload(self):
        self.journalsTable.setDB(self.db)
    
    def openDialog(self):
        ans = QtWidgets.QFileDialog.getOpenFileName(self, self.tr("Select Database"), "",
                                              self.tr("BibTeX VCS configuration files ({})".format(BTVCSCONF)))
        if len(ans[0]) > 0:
            directory = os.path.dirname(ans[0])
            with self.catchExceptions():
                db = Database(directory)
                self.setDB(db)
        
    def cloneDialog(self):
        dialog = CloneDialog(self)
        if dialog.exec_() == dialog.Accepted:
            try:
                db = Database.cloneDatabase(
                        dialog.vcsTypeChooser.currentText(),
                        dialog.urlEdit.text(),
                        dialog.targetEdit.text())
                self.setDB(db)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, self.tr("Error Cloning Repository"),
                                               str(e))     
        
    def updateRepository(self):
        with self.catchExceptions():
            ans = self.db.vcs.update()
            if ans:
                QtWidgets.QMessageBox.information(self,
                    self.tr("Update successful"),
                    self.tr("Successfully merged remote changes"))
                self.reload()
            else:
                QtWidgets.QMessageBox.information(self,
                    self.tr("No updates"),
                    self.tr("No updates found in remote repository"))
        
        
    def jabref(self):
        try:
            subprocess.Popen(["jabref", self.db.bibfilePath])
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, self.tr('JabRef not found'),
                self.tr('The JabRef executable was not found. '
                        'Please install JabRef from http://jabref.sf.net.'))

    def commit(self):
        from bibtexvcs import checks
        self.db.reload()
        self.reload()
        ans = checks.performDatabaseCheck(self.db)
        if len(ans) > 0:
            QtWidgets.QMessageBox.critical(self, self.tr("Checks Failed"),
                                           self.tr("Database consistency check failed:\n\n") +
                                           "\n\n".join(str(a) for a in ans))
            return False
        with self.catchExceptions():
            if not self.db.vcs.commit():
                QtWidgets.QMessageBox.information(self,
                    self.tr("Nothing to commit"),
                    self.tr("There are no local changes."))
            else:
                QtWidgets.QMessageBox.information(self,
                    self.tr("Commit successful"),
                    self.tr("Successfully updated remote repository."))
                self.reload()
        
    def closeEvent(self, event):
        if self.db and self.db.vcs.localChanges():
            ans = QtWidgets.QMessageBox.question(self,
                self.tr("Local changes present"),
                self.tr("Database was modified locally. Are you sure you want to quit "
                        "without committing the changes?"))
            if ans == QtWidgets.QMessageBox.Yes:
                config.saveDefaultDatabase(self.db)
                event.accept()
            else:
                event.ignore()
        else:
            if self.db:
                config.saveDefaultDatabase(self.db)
            event.accept()

app = None
window = None

def run():
    global app, window
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = BtVCSGui()
    try:
        lastDB = config.getDefaultDatabase()
        window.setDB(lastDB)
    except:
        pass
    app.exec_()
    
if __name__ == '__main__':
    run()