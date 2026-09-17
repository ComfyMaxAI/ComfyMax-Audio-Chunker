"""Independent scene-cut editing and audition on the shared timeline."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,
    QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QDoubleSpinBox,QMessageBox)
from .scenes import propose,scene_rows,validate_cuts
from .corrections import EditCommand
from .waveform import timestamp
from .audio import Cursor
from .lyrics_workflow import review_complete,review_fingerprint


class ScenePanel:
    def build_scenes(self):
        self.selected_scene=-1; self.selected_cut=None
        pane=QWidget(); layout=QVBoxLayout(pane)
        bar=QHBoxLayout()
        for label,name,slot in [('Generate proposals','generate_button',self.regenerate_scenes),
                ('Play Scene','scene_play',self.play_scene),('Previous Scene','scene_previous',lambda:self.adjacent_scene(-1)),
                ('Next Scene','scene_next',lambda:self.adjacent_scene(1))]:
            button=QPushButton(label); setattr(self,name,button); button.clicked.connect(slot); bar.addWidget(button)
        bar.addStretch(); layout.addLayout(bar)
        self.scene_table=QTableWidget(0,6)
        self.scene_table.setHorizontalHeaderLabels(['Scene','Start','End','Duration','Corrected lyrics / Instrumental','Warnings'])
        self.scene_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scene_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.scene_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.scene_table.setAlternatingRowColors(True); self.scene_table.setWordWrap(False)
        self.scene_table.verticalHeader().hide()
        for col in range(4): self.scene_table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeToContents)
        self.scene_table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        self.scene_table.setColumnWidth(5,240)
        self.scene_table.itemSelectionChanged.connect(self.scene_selection_changed)
        self.scene_table.cellClicked.connect(lambda *_:self.scene_selection_changed())
        self.scene_table.cellDoubleClicked.connect(lambda *_:self.play_scene())
        layout.addWidget(self.scene_table,1)
        cuts=QHBoxLayout(); self.cut_label=QLabel('Cut position (seconds):'); cuts.addWidget(self.cut_label)
        self.cut_time=QDoubleSpinBox(); self.cut_time.setDecimals(6); self.cut_time.setRange(0,999999); self.cut_time.setSingleStep(.1)
        self.cut_time.setAccessibleName('Scene cut position in seconds'); cuts.addWidget(self.cut_time)
        for label,name,slot in [('Use playhead','cut_playhead',self.cut_from_playhead),('Add Cut','cut_add',self.add_cut),
                              ('Move Cut','cut_move',self.move_cut),('Delete Cut','cut_delete',self.delete_cut)]:
            button=QPushButton(label); setattr(self,name,button); button.clicked.connect(slot); cuts.addWidget(button)
        undo=QPushButton('Undo'); redo=QPushButton('Redo')
        undo.clicked.connect(self.undo_edit); redo.clicked.connect(self.redo_edit)
        self.history.canUndoChanged.connect(undo.setEnabled); self.history.canRedoChanged.connect(redo.setEnabled)
        undo.setEnabled(False); redo.setEnabled(False); cuts.addWidget(undo); cuts.addWidget(redo)
        cuts.addStretch(); layout.addLayout(cuts)
        self.scene_summary=QLabel('Generate proposals to start. Scene cuts never change phrase timestamps.')
        self.scene_summary.setWordWrap(True); layout.addWidget(self.scene_summary)
        self.detail.cutSelected.connect(self.select_cut); self.detail.cutMoved.connect(self.drag_cut)
        self.detail.sceneSelected.connect(self.select_scene)
        return pane

    def has_scenes(self):
        return bool(self.doc and (self.doc.data.get('scenes_initialized') or self.doc.data.get('chunk_boundaries')))

    def refresh_scenes(self):
        rows=scene_rows(self.doc.data,self.doc.analysis) if self.has_scenes() else []
        self.scene_table.blockSignals(True); self.scene_table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            values=[str(i+1),timestamp(row['start']),timestamp(row['end']),f"{row['duration']:.3f} s",row['lyrics'],'; '.join(row['warnings'])]
            for j,value in enumerate(values):
                item=QTableWidgetItem(value.replace('\n',' / ')); item.setToolTip(value)
                if row['duration']>15: item.setBackground(QColor('#ffe0de'))
                self.scene_table.setItem(i,j,item)
        if rows:
            self.selected_scene=max(0,min(self.selected_scene,len(rows)-1)); self.scene_table.selectRow(self.selected_scene)
        else: self.selected_scene=-1
        self.scene_table.blockSignals(False)
        for wave in (self.detail,self.overview):
            wave.scene_index=self.selected_scene; wave.selected_cut=self.selected_cut; wave.update()
        for button in (self.scene_play,self.scene_previous,self.scene_next): button.setEnabled(bool(rows))
        self.cut_delete.setEnabled(self.selected_cut in self.doc.data.get('chunk_boundaries',[]))
        self.cut_move.setEnabled(self.cut_delete.isEnabled())
        self.generate_button.setText('Regenerate Proposals' if rows else 'Generate proposals')
        over=sum(r['duration']>15 for r in rows); flagged=sum(bool(r['warnings']) for r in rows)
        self.scene_summary.setText(f'{len(rows)} scenes • {over} OVER 15 SECONDS • {flagged} scenes to review. Select a scene to edit its ending cut, or drag a marker in the Scene cuts lane.' if rows else
                                  'Generate proposals to start. Scene cuts never change phrase timestamps.')
        if rows and self.doc.data.get('scene_lyrics_fingerprint')!=review_fingerprint(self.doc.data):
            self.scene_summary.setText('Existing scenes are from an earlier lyric version — complete Lyrics Review, then regenerate. '+self.scene_summary.text())
        self.generate_button.setEnabled(review_complete(self.doc.data))

    def scene_state(self):
        return dict(cuts=list(self.doc.data.get('chunk_boundaries',[])),initialized=bool(self.doc.data.get('scenes_initialized')),
                    lyrics_fingerprint=self.doc.data.get('scene_lyrics_fingerprint'))

    def apply_scenes(self,target,state):
        validate_cuts(state['cuts'],self.doc.data['timeline']['frames'])
        if self.transport.active: self.transport.halt()
        self.transport.cursor=Cursor(0,self.transport.total,self.transport.parked,self.loop.isChecked())
        self.audition_range=None
        self.doc.data['chunk_boundaries']=list(state['cuts']); self.doc.data['scenes_initialized']=state['initialized']
        self.doc.data['scene_lyrics_fingerprint']=state.get('lyrics_fingerprint')
        if self.selected_cut not in state['cuts']: self.selected_cut=None
        self.refresh_scenes(); self.update_context(); self.changed()

    def commit_cuts(self,cuts,label,generated=False):
        try: validate_cuts(cuts,self.doc.data['timeline']['frames'])
        except ValueError as exc: QMessageBox.warning(self,'Scene cut',str(exc)); return
        after=dict(cuts=cuts,initialized=True,lyrics_fingerprint=review_fingerprint(self.doc.data) if generated else self.doc.data.get('scene_lyrics_fingerprint'))
        if after==self.scene_state(): return
        self.break_edit_group(); self.history.push(EditCommand(self.apply_scenes,'scenes',self.scene_state(),after,label))

    def regenerate_scenes(self):
        if not self.doc: return
        if not review_complete(self.doc.data):
            QMessageBox.warning(self,'Lyrics review required','Correct, split and review the Lyrics, then choose Lyrics Review Complete.'); return
        if self.has_scenes() and QMessageBox.question(self,'Regenerate proposals',
                'Replace the current scene cuts with new proposals? This can be undone.',QMessageBox.Yes|QMessageBox.Cancel)!=QMessageBox.Yes: return
        try: cuts=propose(self.doc.data,self.doc.analysis)
        except ValueError as exc: QMessageBox.warning(self,'Scene proposals',str(exc)); return
        self.commit_cuts(cuts,'regenerate scene proposals',generated=True)

    def select_scene(self,index):
        if 0<=index<self.scene_table.rowCount():
            self.tabs.setCurrentIndex(1); self.scene_table.selectRow(index); self.scene_selection_changed()

    def scene_selection_changed(self):
        index=self.scene_table.currentRow()
        if not self.doc or index<0: return
        self.selected_scene=index; row=scene_rows(self.doc.data,self.doc.analysis)[index]
        self.selected_cut=row['end_frame'] if row['end_frame']<self.doc.data['timeline']['frames'] else None
        self.cut_time.setValue(row['end']); self.refresh_scenes()
        self.set_view(max(0,row['start']-1),max(8,row['duration']+2))

    def select_cut(self,frame):
        self.tabs.setCurrentIndex(1)
        cuts=self.doc.data.get('chunk_boundaries',[])
        if frame in cuts: self.selected_scene=cuts.index(frame)
        self.selected_cut=frame; self.cut_time.setValue(frame/self.transport.rate)
        self.refresh_scenes()

    def cut_from_playhead(self):
        if self.transport: self.cut_time.setValue(self.transport.position()/self.transport.rate)

    def add_cut(self):
        if not self.doc: return
        frame=round(self.cut_time.value()*self.transport.rate)
        self.commit_cuts(sorted(self.doc.data.get('chunk_boundaries',[])+[frame]),'add scene cut')
        if frame in self.doc.data.get('chunk_boundaries',[]): self.select_cut(frame)

    def move_cut(self):
        if self.selected_cut is not None: self.drag_cut(self.selected_cut,round(self.cut_time.value()*self.transport.rate))

    def drag_cut(self,old,new):
        cuts=list(self.doc.data.get('chunk_boundaries',[]))
        if old not in cuts: return
        index=cuts.index(old); bounds=[0]+cuts+[self.doc.data['timeline']['frames']]
        if not bounds[index]<new<bounds[index+2]:
            QMessageBox.warning(self,'Move Cut','Keep the cut between its two neighboring boundaries.'); return
        cuts[index]=new; self.commit_cuts(cuts,'move scene cut'); self.select_cut(new)

    def delete_cut(self):
        if self.selected_cut is not None:
            self.commit_cuts([c for c in self.doc.data.get('chunk_boundaries',[]) if c!=self.selected_cut],'delete scene cut')

    def play_scene(self):
        if not self.has_scenes() or self.selected_scene<0: return
        row=scene_rows(self.doc.data,self.doc.analysis)[self.selected_scene]
        for wave in (self.detail,self.overview): wave.selected=-1
        self.audition_range=(row['start'],row['end']); self.update_context()
        self.safe(lambda:self.transport.play(row['start_frame'],row['end_frame'],loop=self.loop.isChecked()))
        self.hint.setText(f"Scene {row['scene']} • {timestamp(row['start'])} – {timestamp(row['end'])} • exact scene bounds, no phrase context")

    def adjacent_scene(self,direction):
        if self.scene_table.rowCount():
            index=max(0,min(self.scene_table.rowCount()-1,self.selected_scene+direction))
            self.scene_table.selectRow(index); self.play_scene(); self.scene_table.scrollToItem(self.scene_table.item(index,0))
