"""Milestone 2 widgets and command wiring, separate from the audio transport."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack, QTextCursor
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QTextEdit,
    QPushButton, QCheckBox, QSplitter, QFileDialog, QMessageBox, QLineEdit)
from .corrections import CorrectionText, EditCommand, effective_text, correction_state, edited_state
from .waveform import timestamp


class CorrectionPanel:
    def build_corrections(self, layout):
        self._edit_epoch = 0
        self._applying_edit = False
        self.history = QUndoStack(self)
        self.phrase_heading = QLabel('Select a phrase to compare and correct its lyrics.')
        layout.addWidget(self.phrase_heading)
        pair = QSplitter(Qt.Horizontal)
        self.original = QTextEdit(); self.original.setReadOnly(True)
        self.original.setAccessibleName('Original Whisper text')
        self.corrected = CorrectionText(); self.corrected.setEnabled(False)
        self.corrected.setAccessibleName('Corrected phrase text')
        self.corrected.setPlaceholderText('Select a phrase. Corrections keep its timestamps.')
        for label,editor in [('Whisper original — preserved',self.original),('Your correction',self.corrected)]:
            pane=QWidget(); box=QVBoxLayout(pane); box.setContentsMargins(0,0,0,0)
            box.addWidget(QLabel(label)); editor.setMinimumHeight(75); editor.setMaximumHeight(120)
            box.addWidget(editor); pair.addWidget(pane)
        layout.addWidget(pair)
        self.alignment_label=QLabel('Timing locked. Original word timings remain available in the project.')
        self.alignment_label.setWordWrap(True); layout.addWidget(self.alignment_label)
        actions=QHBoxLayout()
        self.review_button=QPushButton('Mark Reviewed'); self.restore_button=QPushButton('Restore Original')
        self.undo_button=QPushButton('Undo'); self.redo_button=QPushButton('Redo')
        self.reference_toggle=QCheckBox('Reference Lyrics')
        for button in (self.review_button,self.restore_button,self.undo_button,self.redo_button):
            actions.addWidget(button); button.setEnabled(False)
        actions.addStretch(); actions.addWidget(self.reference_toggle); layout.addLayout(actions)
        self.review_button.clicked.connect(self.mark_reviewed)
        self.restore_button.clicked.connect(self.restore_original)
        self.undo_button.clicked.connect(self.undo_edit); self.redo_button.clicked.connect(self.redo_edit)
        self.history.canUndoChanged.connect(self.undo_button.setEnabled)
        self.history.canRedoChanged.connect(self.redo_button.setEnabled)
        self.history.undoTextChanged.connect(self.undo_button.setToolTip)
        self.history.redoTextChanged.connect(self.redo_button.setToolTip)
        self.corrected.textChanged.connect(self.correction_changed)

        self.reference_panel=QWidget(); reference_layout=QVBoxLayout(self.reference_panel)
        reference_layout.setContentsMargins(8,0,0,0)
        label=QLabel('Reference lyrics — not aligned'); label.setWordWrap(True); reference_layout.addWidget(label)
        toolbar=QHBoxLayout()
        self.load_reference_button=QPushButton('Load text…'); toolbar.addWidget(self.load_reference_button)
        self.reference_find=QLineEdit(); self.reference_find.setPlaceholderText('Find in lyrics')
        self.reference_find.setAccessibleName('Find in reference lyrics'); toolbar.addWidget(self.reference_find,1)
        self.find_button=QPushButton('Find next'); toolbar.addWidget(self.find_button)
        reference_layout.addLayout(toolbar)
        self.reference=CorrectionText(); self.reference.setMinimumWidth(240)
        self.reference.setAccessibleName('Reference lyrics text')
        self.reference.setPlaceholderText('Paste the complete known lyrics here, or load a UTF-8 text file.\n\nSelect just the words for one phrase, then apply explicitly.')
        reference_layout.addWidget(self.reference,1)
        self.apply_reference_button=QPushButton('Apply selection to selected phrase'); self.apply_reference_button.setEnabled(False)
        reference_layout.addWidget(self.apply_reference_button)
        note=QLabel('Reference text has no timestamps. Applying it changes only the selected phrase’s correction.')
        note.setWordWrap(True); reference_layout.addWidget(note)
        self.reference_panel.hide()
        self.reference_toggle.toggled.connect(self.reference_visibility)
        self.load_reference_button.clicked.connect(self.load_reference)
        self.find_button.clicked.connect(self.find_reference)
        self.reference_find.returnPressed.connect(self.find_reference)
        self.reference.selectionChanged.connect(self.reference_selection_changed)
        self.reference.textChanged.connect(self.reference_changed)
        self.apply_reference_button.clicked.connect(self.apply_reference)
        for editor in (self.corrected,self.reference):
            editor.undoRequested.connect(self.undo_edit); editor.redoRequested.connect(self.redo_edit)
            editor.boundary.connect(self.break_edit_group)
            editor.can_undo=self.history.canUndo; editor.can_redo=self.history.canRedo

    def break_edit_group(self):
        self._edit_epoch += 1

    def reset_corrections(self):
        self.history.clear(); self.break_edit_group()
        self.reference.blockSignals(True)
        self.reference.setPlainText(self.doc.data.get('reference_lyrics',''))
        self.reference.blockSignals(False)
        self.corrected.blockSignals(True); self.corrected.clear(); self.corrected.blockSignals(False)
        self.original.clear(); self.corrected.setEnabled(False)
        self.reference_toggle.blockSignals(True)
        visible=bool(self.doc.data.get('view',{}).get('reference_visible',False))
        self.reference_toggle.setChecked(visible); self.reference_panel.setVisible(visible)
        self.reference_toggle.blockSignals(False)
        self.reference_selection_changed()

    def row_status(self,phrase):
        pieces=['Reviewed' if phrase['review_status']=='reviewed' else 'Unreviewed']
        if phrase['end']-phrase['start']>15+1e-9: pieces.insert(0,'OVER 15 SECONDS')
        if phrase.get('corrected_text') is not None: pieces.append('Edited')
        if phrase.get('suspect'): pieces.append('Whisper uncertain')
        return ' • '.join(pieces)

    def refresh_correction(self):
        if not self.doc or self.selected<0: return
        phrase=self.doc.phrases[self.selected]
        self.phrase_heading.setText(f'Phrase {self.selected+1} • {timestamp(phrase["start"])} – {timestamp(phrase["end"])} • {phrase["end"]-phrase["start"]:.3f} s • '+('OVER 15 SECONDS — split required' if phrase['end']-phrase['start']>15+1e-9 else 'Text edits keep timing'))
        self.original.setPlainText(phrase['original_text'])
        text=effective_text(phrase)
        if self.corrected.toPlainText()!=text:
            position=self.corrected.textCursor().position()
            self.corrected.blockSignals(True); self.corrected.setPlainText(text)
            cursor=self.corrected.textCursor(); cursor.setPosition(min(position,len(text))); self.corrected.setTextCursor(cursor)
            self.corrected.blockSignals(False)
        self.corrected.setEnabled(True)
        self.review_button.setEnabled(phrase['review_status']!='reviewed')
        self.restore_button.setEnabled(phrase.get('corrected_text') is not None)
        self.restore_button.setText('Restore Split Text' if 'lineage' in phrase else 'Restore Original')
        self.alignment_label.setText('Phrase timed; corrected words not individually aligned.' if phrase.get('corrected_text') is not None else
                                     'Original Whisper word timings are estimates. Timing locked.')
        self.reference_selection_changed()
        if 'lineage' in phrase:
            self.alignment_label.setText('Split phrase • left pane shows full original Whisper evidence. Corrected words have no individual alignment.')

    def _apply_edit(self,target,state):
        self._applying_edit=True
        try:
            if target=='reference':
                self.doc.data['reference_lyrics']=state
                if self.reference.toPlainText()!=state:
                    self.reference.blockSignals(True); self.reference.setPlainText(state); self.reference.blockSignals(False)
            else:
                self.doc.set_correction_state(target,state)
                row=next(i for i,p in enumerate(self.doc.phrases) if p['id']==target)
                phrase=self.doc.phrases[row]
                self.table.item(row,4).setText(effective_text(phrase))
                self.table.item(row,4).setToolTip(effective_text(phrase))
                self.table.item(row,5).setText(self.row_status(phrase))
                if self.selected==row: self.refresh_correction()
        finally:
            self._applying_edit=False
        self.refresh_scenes()
        self.refresh_review()
        self.update_split_preview()
        self.changed()

    def push_phrase(self,after,label,typing=False):
        if not self.doc or self.selected<0: return
        phrase=self.doc.phrases[self.selected]; before=correction_state(phrase)
        if before==after: return
        if not typing: self.break_edit_group()
        self.history.push(EditCommand(self._apply_edit,phrase['id'],before,after,label,
                                      self._edit_epoch if typing else None))

    def correction_changed(self):
        if self._applying_edit or self.loading or not self.doc or self.selected<0: return
        phrase=self.doc.phrases[self.selected]; text=self.corrected.toPlainText()
        if text==effective_text(phrase): return
        self.push_phrase(edited_state(phrase,text),f'edit phrase {self.selected+1}',True)

    def reference_changed(self):
        if self._applying_edit or self.loading or not self.doc: return
        before=self.doc.data.get('reference_lyrics',''); after=self.reference.toPlainText()
        if before!=after:
            self.history.push(EditCommand(self._apply_edit,'reference',before,after,'edit reference lyrics',self._edit_epoch))

    def mark_reviewed(self):
        if self.doc and self.selected>=0:
            after=correction_state(self.doc.phrases[self.selected]); after['review_status']='reviewed'
            self.push_phrase(after,f'mark phrase {self.selected+1} reviewed')

    def restore_original(self):
        if self.doc and self.selected>=0:
            phrase=self.doc.phrases[self.selected]
            self.push_phrase(edited_state(phrase,phrase.get('split_baseline_text')),f'restore phrase {self.selected+1}')

    def reference_visibility(self,value):
        self.reference_panel.setVisible(value)
        if self.doc:
            self.doc.data['view']['reference_visible']=value; self.changed()

    def reference_selection_changed(self):
        self.apply_reference_button.setEnabled(self.doc is not None and self.selected>=0 and self.reference.textCursor().hasSelection())

    def apply_reference(self):
        if not self.doc or self.selected<0 or not self.reference.textCursor().hasSelection(): return
        text=self.reference.textCursor().selectedText().replace('\u2029','\n').replace('\u2028','\n')
        self.push_phrase(edited_state(self.doc.phrases[self.selected],text),f'apply reference to phrase {self.selected+1}')

    def replace_reference(self,text):
        self.break_edit_group()
        before=self.doc.data.get('reference_lyrics','')
        if before!=text:
            self.history.push(EditCommand(self._apply_edit,'reference',before,text,'load reference lyrics'))

    def load_reference(self):
        if not self.doc: return
        path,_=QFileDialog.getOpenFileName(self,'Load reference lyrics (UTF-8)',str(self.doc.root),'Text files (*.txt);;All files (*)')
        if not path: return
        try:
            text=Path(path).read_text(encoding='utf-8-sig')
            self.replace_reference(text)
        except (OSError,UnicodeError) as exc:
            QMessageBox.warning(self,'Cannot load lyrics',f'Use a UTF-8 text file. {exc}')

    def find_reference(self):
        text=self.reference_find.text()
        if not text: return
        if not self.reference.find(text):
            cursor=self.reference.textCursor(); cursor.movePosition(QTextCursor.Start); self.reference.setTextCursor(cursor)
            self.reference.find(text)

    def move_to_command(self,command):
        if command and command.target not in ('reference','scenes','phrase_structure','lyrics_review'):
            row=next(i for i,p in enumerate(self.doc.phrases) if p['id']==command.target)
            if self.selected!=row: self.table.selectRow(row); self.table.scrollToItem(self.table.item(row,0))

    def undo_edit(self):
        self.break_edit_group()
        if self.history.canUndo():
            self.move_to_command(self.history.command(self.history.index()-1))
            self.history.undo()

    def redo_edit(self):
        self.break_edit_group()
        if self.history.canRedo():
            self.move_to_command(self.history.command(self.history.index()))
            self.history.redo()
