"""Phrase structure controls and explicit whole-lyrics review."""
import copy
import math
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QTextCursor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QDoubleSpinBox,QMessageBox,QTableWidgetItem
from .lyrics_workflow import split_state,review_issues,review_complete,review_fingerprint
from .corrections import EditCommand,effective_text
from .project import playable
from .waveform import timestamp
from .audio import Cursor


class PhrasePanel:
    def build_phrase_workflow(self,layout):
        bar=QHBoxLayout(); self.split_button=QPushButton('Split Phrase')
        self.complete_button=QPushButton('Lyrics Review Complete')
        self.review_label=QLabel('Lyrics review incomplete'); self.review_label.setWordWrap(True)
        bar.addWidget(self.split_button); bar.addWidget(self.complete_button); bar.addWidget(self.review_label,1)
        layout.addLayout(bar)
        self.split_panel=QWidget(); box=QVBoxLayout(self.split_panel); box.setContentsMargins(0,0,0,0)
        note=QLabel('Place the cursor in Your correction at the text split. Choose the corresponding audio time independently; no word times are guessed.')
        note.setWordWrap(True); box.addWidget(note)
        row=QHBoxLayout(); row.addWidget(QLabel('Split at song time (seconds):'))
        self.split_time=QDoubleSpinBox(); self.split_time.setDecimals(6); self.split_time.setRange(0,999999); self.split_time.setSingleStep(.05)
        row.addWidget(self.split_time)
        for label,name,slot in [('Use playhead','split_playhead',self.split_at_playhead),('Listen around split','split_listen',self.listen_split),
                               ('Confirm Split','split_confirm',self.confirm_split),('Cancel','split_cancel',self.cancel_split)]:
            button=QPushButton(label); setattr(self,name,button); button.clicked.connect(slot); row.addWidget(button)
        box.addLayout(row)
        self.split_preview=QLabel(); self.split_preview.setWordWrap(True); box.addWidget(self.split_preview)
        layout.addWidget(self.split_panel); self.split_panel.hide(); self.split_phrase_id=None
        self.split_button.clicked.connect(self.begin_split); self.complete_button.clicked.connect(self.complete_review)
        self.corrected.cursorPositionChanged.connect(self.update_split_preview)
        self.split_time.valueChanged.connect(self.update_split_preview)

    def refresh_phrase_table(self):
        self.table.blockSignals(True); self.table.setRowCount(len(self.doc.phrases))
        for row,p in enumerate(self.doc.phrases):
            valid=playable(p,self.doc.duration)
            duration=p['end']-p['start'] if all(isinstance(p[k],(int,float)) and math.isfinite(p[k]) for k in ('start','end')) else None
            values=['▶',timestamp(p['start']),timestamp(p['end']),f'{duration:.3f} s' if duration is not None else 'Invalid',
                    effective_text(p),'Invalid timing' if not valid else self.row_status(p)]
            for col,text in enumerate(values):
                item=QTableWidgetItem(text); item.setToolTip(text)
                if duration is not None and duration>15+1e-9:
                    item.setBackground(QColor('#ffe0de')); item.setToolTip(text+' • OVER 15 SECONDS — Split Phrase before completing review')
                self.table.setItem(row,col,item)
        if 0<=self.selected<len(self.doc.phrases): self.table.selectRow(self.selected)
        self.table.blockSignals(False)
        self.count_label.setText(f'{len(self.doc.phrases)} lyric phrases • click a row to audition • red rows exceed 15 seconds')

    def refresh_review(self):
        if not self.doc: return
        complete=review_complete(self.doc.data); issues=review_issues(self.doc.data)
        self.review_label.setText('Lyrics Review Complete' if complete else
                                 f'Lyrics review incomplete • {len(issues)} checks remaining' if issues else
                                 'All phrases reviewed • confirm Lyrics Review Complete')
        self.review_label.setToolTip('\n'.join(issues) if issues else 'Text or timing changes reopen review; undo can restore the completed version.')
        self.complete_button.setEnabled(not complete)
        self.generate_button.setEnabled(complete)
        self.generate_button.setToolTip('Generate from reviewed phrases' if complete else 'Complete the Lyrics review first.')

    def apply_review(self,target,state):
        self.doc.data['lyrics_review']=copy.deepcopy(state); self.refresh_review(); self.refresh_scenes(); self.changed()

    def complete_review(self):
        issues=review_issues(self.doc.data)
        if issues:
            QMessageBox.warning(self,'Lyrics review incomplete','Review every phrase and split phrases over 15 seconds first.\n\n'+'\n'.join(issues[:12]))
            return
        self.break_edit_group()
        self.history.push(EditCommand(self.apply_review,'lyrics_review',self.doc.data.get('lyrics_review'),
                                      {'fingerprint':review_fingerprint(self.doc.data)},'complete lyrics review'))

    def begin_split(self):
        if not self.doc or self.selected<0: return
        p=self.doc.phrases[self.selected]
        if not playable(p,self.doc.duration):
            QMessageBox.warning(self,'Split Phrase','This phrase needs valid timing before it can be split.'); return
        self.split_phrase_id=p['id']; self.split_panel.show()
        self.split_time.setValue(p['start']); self.update_split_preview()
        QTimer.singleShot(0,lambda:self.lyrics_scroll.ensureWidgetVisible(self.split_panel))

    def cancel_split(self):
        self.split_phrase_id=None; self.split_panel.hide()
        for wave in (self.detail,self.overview): wave.split_position=None; wave.update()

    def split_at_playhead(self):
        self.split_time.setValue(self.transport.position()/self.transport.rate)

    def split_arguments(self):
        if self.selected<0 or self.doc.phrases[self.selected]['id']!=self.split_phrase_id: raise ValueError('Select a phrase to split.')
        cursor=self.corrected.textCursor()
        if cursor.hasSelection(): raise ValueError('Use a single text cursor position, not a selected range.')
        # Qt positions count UTF-16 units. Obtain the actual prefix instead of
        # slicing a Python string with that offset (important for emoji).
        prefix=QTextCursor(cursor); prefix.setPosition(0,QTextCursor.KeepAnchor)
        index=len(prefix.selectedText().replace('\u2029','\n').replace('\u2028','\n'))
        return self.split_phrase_id,index,round(self.split_time.value()*self.transport.rate)

    def update_split_preview(self):
        if not getattr(self,'split_phrase_id',None) or not self.doc: return
        frame=round(self.split_time.value()*self.transport.rate)
        for wave in (self.detail,self.overview): wave.split_position=frame/self.transport.rate; wave.update()
        try:
            args=self.split_arguments(); state=split_state(self.doc.data,*args)
            children=[p for p in state['phrases'] if p.get('lineage',{}).get('parent_id')==self.split_phrase_id]
            self.split_preview.setText(' | '.join(f"{timestamp(p['start'])}–{timestamp(p['end'])} ({p['end']-p['start']:.3f}s): {effective_text(p)[:90]}" for p in children))
            self.split_confirm.setEnabled(True)
        except ValueError as exc:
            self.split_preview.setText(str(exc)); self.split_confirm.setEnabled(False)

    def listen_split(self):
        p=self.doc.phrases[self.selected]; seconds=self.split_time.value()
        if not p['start']<seconds<p['end']:
            QMessageBox.warning(self,'Split Phrase','Choose a time inside this phrase.'); return
        self.select_range(max(p['start'],seconds-1.5),min(p['end'],seconds+1.5))

    def phrase_structure(self):
        return dict(phrases=copy.deepcopy(self.doc.phrases),phrase_history=copy.deepcopy(self.doc.data.get('phrase_history',[])),
                    selected_id=self.doc.phrases[self.selected]['id'] if self.selected>=0 else None)

    def apply_phrase_structure(self,target,state):
        self.transport.halt(); self.transport.cursor=Cursor(0,self.transport.total,self.transport.parked,self.loop.isChecked())
        self.cancel_split(); self.audition_range=None
        self.doc.data['phrases']=copy.deepcopy(state['phrases']); self.doc.data['phrase_history']=copy.deepcopy(state['phrase_history'])
        self.selected=next((i for i,p in enumerate(self.doc.phrases) if p['id']==state['selected_id']),0)
        self.refresh_phrase_table(); self.selection_changed(); self.refresh_review(); self.refresh_scenes(); self.changed()

    def confirm_split(self):
        try: after=split_state(self.doc.data,*self.split_arguments())
        except ValueError as exc: QMessageBox.warning(self,'Split Phrase',str(exc)); return
        self.break_edit_group(); self.history.push(EditCommand(self.apply_phrase_structure,'phrase_structure',self.phrase_structure(),after,'split lyric phrase'))
