'use client';

import React, { useEffect, useState } from 'react';
import { Loader2, NotebookPen, Pencil, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/app/components/ui/tooltip';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const TRUNCATE_LEN = 100;

type NoteField = 'sourcer_note' | 'recruiter_note';
type ViewerRole = 'sourcer' | 'recruiter';

interface Props {
  appearanceId: string;
  sourcerNote: string | null | undefined;
  recruiterNote: string | null | undefined;
  viewerRole: ViewerRole;
  sourcerName: string;
  recruiterName: string;
  onSaved: (field: NoteField, note: string) => void;
}

function hasNoteContent(note: string | null | undefined): boolean {
  return Boolean(note?.trim());
}

function NoteReadModal({
  open, onClose, authorName, note,
}: { open: boolean; onClose: () => void; authorName: string; note: string }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-black/60"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            className="fixed left-1/2 top-1/2 z-[61] w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#0f1419] p-5 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3 mb-4">
              <h3 className="text-sm font-semibold text-white">Note de {authorName}</h3>
              <button
                type="button"
                onClick={onClose}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{note}</p>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function NoteContent({ note, authorLabel }: { note: string; authorLabel: string }) {
  const [modalOpen, setModalOpen] = useState(false);
  const needsTruncate = note.length > TRUNCATE_LEN;

  if (!needsTruncate) {
    return <p className="text-sm text-slate-400 italic leading-relaxed">{note}</p>;
  }

  return (
    <>
      <p className="text-sm text-slate-400 italic leading-relaxed">
        {note.slice(0, TRUNCATE_LEN)}…{' '}
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="text-xs text-teal-400 hover:text-teal-300 not-italic transition-colors"
        >
          Lire la suite
        </button>
      </p>
      <NoteReadModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        authorName={authorLabel}
        note={note}
      />
    </>
  );
}

function NoteIconButton({
  hasNote, onClick,
}: { hasNote: boolean; onClick: () => void }) {
  const Icon = hasNote ? Pencil : NotebookPen;
  const tooltip = hasNote ? 'Modifier la note' : 'Ajouter une note';

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          className="p-1 rounded-md text-teal-400 hover:text-teal-300 hover:bg-teal-400/10 transition-colors"
        >
          <Icon className="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="bg-slate-800 text-white border border-white/10 text-xs"
      >
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}

interface NoteEditorProps {
  appearanceId: string;
  field: NoteField;
  initialNote: string;
  onSaved: (field: NoteField, note: string) => void;
  onCancel: () => void;
}

function NoteEditor({ appearanceId, field, initialNote, onSaved, onCancel }: NoteEditorProps) {
  const [draft, setDraft] = useState(initialNote);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/candidates/appearances/${appearanceId}/note`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: draft }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `Erreur ${res.status}`);
      }
      const d = await res.json();
      onSaved(field, d.appearance?.[field] ?? draft);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur lors de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        value={draft}
        onChange={e => setDraft(e.target.value)}
        rows={3}
        autoFocus
        className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-[#1f9d94]/50 focus:outline-none resize-y min-h-[72px]"
        placeholder="Votre note pour cette offre…"
      />
      {error && <p className="text-xs text-red-300">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="px-3 py-1.5 rounded-lg bg-[#1f9d94] hover:bg-[#25afa5] text-white text-xs font-medium disabled:opacity-60"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Enregistrer'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-400 hover:text-white text-xs"
        >
          Annuler
        </button>
      </div>
    </div>
  );
}

interface DisplayBlock {
  field: NoteField;
  authorLabel: string;
  roleBadge: string;
  note: string;
  canEdit: boolean;
}

function NoteDisplayBlock({
  block,
  appearanceId,
  editing,
  onStartEdit,
  onSaved,
  onCancelEdit,
}: {
  block: DisplayBlock;
  appearanceId: string;
  editing: boolean;
  onStartEdit: () => void;
  onSaved: (field: NoteField, note: string) => void;
  onCancelEdit: () => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-slate-300">{block.authorLabel}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-500/15 text-slate-500">
          {block.roleBadge}
        </span>
        {block.canEdit && !editing && (
          <NoteIconButton hasNote onClick={onStartEdit} />
        )}
      </div>
      {editing ? (
        <NoteEditor
          appearanceId={appearanceId}
          field={block.field}
          initialNote={block.note}
          onSaved={onSaved}
          onCancel={onCancelEdit}
        />
      ) : (
        <NoteContent note={block.note} authorLabel={block.authorLabel} />
      )}
    </div>
  );
}

export function OfferAppearanceNotes({
  appearanceId,
  sourcerNote,
  recruiterNote,
  viewerRole,
  sourcerName,
  recruiterName,
  onSaved,
}: Props) {
  const [editingField, setEditingField] = useState<NoteField | null>(null);
  const [composingNew, setComposingNew] = useState(false);

  const ownField: NoteField = viewerRole === 'sourcer' ? 'sourcer_note' : 'recruiter_note';
  const ownNote = viewerRole === 'sourcer' ? sourcerNote : recruiterNote;
  const ownHasNote = hasNoteContent(ownNote);

  const displayBlocks: DisplayBlock[] = [];

  if (hasNoteContent(sourcerNote)) {
    displayBlocks.push({
      field: 'sourcer_note',
      authorLabel: viewerRole === 'sourcer' ? 'Moi' : sourcerName,
      roleBadge: 'Sourceur',
      note: sourcerNote!.trim(),
      canEdit: viewerRole === 'sourcer',
    });
  }

  if (hasNoteContent(recruiterNote)) {
    displayBlocks.push({
      field: 'recruiter_note',
      authorLabel: viewerRole === 'recruiter' ? 'Moi' : recruiterName,
      roleBadge: 'Recruteur',
      note: recruiterNote!.trim(),
      canEdit: viewerRole === 'recruiter',
    });
  }

  // Re-order: on sourcer page own note first; on recruiter page own note last.
  if (viewerRole === 'sourcer') {
    displayBlocks.sort((a, b) => {
      if (a.field === 'sourcer_note') return -1;
      if (b.field === 'sourcer_note') return 1;
      return 0;
    });
  } else {
    displayBlocks.sort((a, b) => {
      if (a.field === 'recruiter_note') return 1;
      if (b.field === 'recruiter_note') return -1;
      return 0;
    });
  }

  const hasAnyNote = displayBlocks.length > 0;
  const showAddIcon = !ownHasNote && !composingNew && editingField === null;

  if (!hasAnyNote && !showAddIcon && !composingNew) return null;

  function handleSaved(field: NoteField, note: string) {
    setEditingField(null);
    setComposingNew(false);
    onSaved(field, note);
  }

  function handleCancel() {
    setEditingField(null);
    setComposingNew(false);
  }

  return (
    <div className="space-y-3" onClick={e => e.stopPropagation()}>
      {displayBlocks.map(block => (
        <NoteDisplayBlock
          key={block.field}
          block={block}
          appearanceId={appearanceId}
          editing={editingField === block.field}
          onStartEdit={() => setEditingField(block.field)}
          onSaved={handleSaved}
          onCancelEdit={handleCancel}
        />
      ))}

      {showAddIcon && (
        <NoteIconButton hasNote={false} onClick={() => setComposingNew(true)} />
      )}

      {composingNew && (
        <NoteEditor
          appearanceId={appearanceId}
          field={ownField}
          initialNote=""
          onSaved={handleSaved}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}

/** @deprecated Use OfferAppearanceNotes */
export const OfferScopedNote = OfferAppearanceNotes;

