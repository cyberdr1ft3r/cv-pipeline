'use client';

import React, { useState } from 'react';
import { MessageSquarePlus, Pencil, Trash2 } from 'lucide-react';
import { DarkSelect } from '@/components/DarkSelect';
import { BTN_PRIMARY, BTN_PRIMARY_SM, TEXTAREA_CLASS } from '@/lib/uiTokens';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export interface CandidateNote {
  id: string;
  author_id?: string | null;
  author_name: string;
  author_role?: string;
  note_type: string;
  content: string;
}

interface NoteTypeOption {
  id: string;
  label: string;
}

interface Props {
  candidateId: string;
  notes: CandidateNote[];
  noteTypes: NoteTypeOption[];
  currentUserId?: string | null;
  isAdmin?: boolean;
  onChanged: () => void;
}

export function CandidateNotesList({
  candidateId,
  notes,
  noteTypes,
  currentUserId,
  isAdmin = false,
  onChanged,
}: Props) {
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [noteType, setNoteType] = useState(noteTypes[0]?.id || 'general');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editType, setEditType] = useState('general');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const typeOptions = noteTypes.map(t => ({ value: t.id, label: t.label }));

  async function addNote() {
    if (!noteContent.trim()) return;
    await fetch(`${API_BASE}/candidates/${candidateId}/notes`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: noteContent, note_type: noteType }),
    });
    setNoteContent('');
    setShowNoteForm(false);
    onChanged();
  }

  async function saveEdit(noteId: string) {
    if (!editContent.trim()) return;
    await fetch(`${API_BASE}/candidates/${candidateId}/notes/${noteId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: editContent, note_type: editType }),
    });
    setEditingId(null);
    onChanged();
  }

  async function confirmDelete(noteId: string) {
    await fetch(`${API_BASE}/candidates/${candidateId}/notes/${noteId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    setConfirmDeleteId(null);
    onChanged();
  }

  function startEdit(note: CandidateNote) {
    setEditingId(note.id);
    setEditContent(note.content);
    setEditType(note.note_type);
    setConfirmDeleteId(null);
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">Notes</h2>
        <button
          type="button"
          onClick={() => setShowNoteForm(!showNoteForm)}
          className="flex items-center gap-1.5 text-xs text-[#1f9d94] hover:text-[#25afa5] transition-colors"
        >
          <MessageSquarePlus className="h-4 w-4" /> Ajouter une note
        </button>
      </div>
      {showNoteForm && (
        <div className="space-y-2">
          <DarkSelect
            value={noteType}
            onChange={setNoteType}
            options={typeOptions}
            className="w-full sm:w-auto"
          />
          <textarea
            value={noteContent}
            onChange={e => setNoteContent(e.target.value)}
            rows={3}
            placeholder="Votre note…"
            className={TEXTAREA_CLASS}
          />
          <button type="button" onClick={addNote} className={BTN_PRIMARY}>
            Enregistrer
          </button>
        </div>
      )}
      {notes.length === 0 && !showNoteForm && (
        <p className="text-slate-500 text-sm">Aucune note pour le moment.</p>
      )}
      {notes.map(n => {
        const isAuthor = currentUserId && n.author_id === currentUserId;
        const canDelete = isAuthor || isAdmin;
        const isEditing = editingId === n.id;
        const isConfirmingDelete = confirmDeleteId === n.id;

        return (
          <div key={n.id} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="text-slate-300">{n.author_name}</span>
                {n.author_role && <span>({n.author_role})</span>}
                <span>· {noteTypes.find(t => t.id === n.note_type)?.label || n.note_type}</span>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {isAuthor && !isEditing && !isConfirmingDelete && (
                  <button
                    type="button"
                    onClick={() => startEdit(n)}
                    className="p-1 text-slate-500 hover:text-white transition-colors"
                    title="Modifier"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                )}
                {canDelete && !isEditing && !isConfirmingDelete && (
                  <button
                    type="button"
                    onClick={() => { setConfirmDeleteId(n.id); setEditingId(null); }}
                    className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                    title="Supprimer"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
            {isConfirmingDelete ? (
              <div className="space-y-2">
                <p className="text-sm text-slate-400">Supprimer cette note ?</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => confirmDelete(n.id)}
                    className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-300 text-xs hover:bg-red-500/30 transition-colors"
                  >
                    Confirmer
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteId(null)}
                    className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-400 text-xs hover:text-white transition-colors"
                  >
                    Annuler
                  </button>
                </div>
              </div>
            ) : isEditing ? (
              <div className="space-y-2">
                <DarkSelect
                  value={editType}
                  onChange={setEditType}
                  options={typeOptions}
                  className="w-full"
                />
                <textarea
                  value={editContent}
                  onChange={e => setEditContent(e.target.value)}
                  rows={3}
                  className={TEXTAREA_CLASS}
                />
                <div className="flex gap-2">
                  <button type="button" onClick={() => saveEdit(n.id)} className={BTN_PRIMARY_SM}>
                    Enregistrer
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-400 text-xs hover:text-white transition-colors"
                  >
                    Annuler
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-300 leading-relaxed">{n.content}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

