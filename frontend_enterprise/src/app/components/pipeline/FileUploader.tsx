import React, { useCallback, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { FileText, Upload, X } from 'lucide-react';

type UploadMode = 'combined' | 'offer';
type UploadTarget = 'cv' | 'offer';

interface FileUploaderProps {
  mode?: UploadMode;
  cvFiles?: File[];
  offerFile?: File | null;
  onCVsSelected?: (files: File[]) => void;
  onOfferSelected?: (file: File) => void;
  onRemoveCV?: (index: number) => void;
  onRemoveOffer?: () => void;
  isLoading?: boolean;
  maxFiles?: number;
}

interface DropzoneConfig {
  title: string;
  description: string;
  formats: string;
  target: UploadTarget;
  accept: string;
  multiple: boolean;
  accentClassName: string;
}

const CV_ACCEPT = '.pdf,.doc,.docx';
const OFFER_ACCEPT = '.txt,.pdf,.doc,.docx,.jpg,.jpeg,.png,.xlsx,.xls,.xlsm';

const DROPZONE_STYLES = {
  base:
    'group relative flex min-h-[192px] items-center justify-center overflow-hidden rounded-[28px] border border-dashed px-6 py-10 transition-all duration-200',
  idle: 'border-white/18 bg-[#1a2240]/78 hover:border-cyan-400/50 hover:bg-[#1d2949]/88',
  active: 'border-cyan-400/70 bg-[#1a3050]/92 shadow-[0_0_0_1px_rgba(45,212,191,0.22)]',
};

const PANEL_STYLES =
  'rounded-[18px] border border-white/10 bg-white/[0.04] px-4 py-3 text-left';

function isAcceptedFile(file: File, accept: string) {
  const normalizedName = file.name.toLowerCase();
  return accept.split(',').some((extension) => normalizedName.endsWith(extension.trim()));
}

export function FileUploader({
  mode = 'combined',
  cvFiles = [],
  offerFile = null,
  onCVsSelected,
  onOfferSelected,
  onRemoveCV,
  onRemoveOffer,
  isLoading = false,
  maxFiles = 10,
}: FileUploaderProps) {
  const [activeTarget, setActiveTarget] = useState<UploadTarget | null>(null);

  const dropzones = useMemo<DropzoneConfig[]>(() => {
    const commonOfferZone: DropzoneConfig = {
      title: "T\u00e9l\u00e9charger l'offre d'emploi",
      description: "D\u00e9posez l'offre d'emploi ou cliquez pour t\u00e9l\u00e9charger",
      formats: 'TXT, PDF, Word (DOC, DOCX), Images (JPG, PNG), Excel (XLSX, XLS, XLSM)',
      target: 'offer',
      accept: OFFER_ACCEPT,
      multiple: false,
      accentClassName: 'text-cyan-300',
    };

    if (mode === 'offer') {
      return [commonOfferZone];
    }

    return [
      {
        title: 'T\u00e9l\u00e9charger les CVs',
        description: 'D\u00e9posez les fichiers CV ou cliquez pour t\u00e9l\u00e9charger',
        formats: 'PDF, DOC, DOCX',
        target: 'cv',
        accept: CV_ACCEPT,
        multiple: true,
        accentClassName: 'text-cyan-300',
      },
      commonOfferZone,
    ];
  }, [mode]);

  const handleDragState = useCallback(
    (event: React.DragEvent, target: UploadTarget | null) => {
      event.preventDefault();
      event.stopPropagation();

      if (event.type === 'dragenter' || event.type === 'dragover') {
        setActiveTarget(target);
        return;
      }

      setActiveTarget(null);
    },
    []
  );

  const handleFiles = useCallback(
    (target: UploadTarget, selectedFiles: File[]) => {
      if (target === 'cv') {
        const validFiles = selectedFiles.filter((file) => isAcceptedFile(file, CV_ACCEPT));
        const mergedFiles = [...cvFiles, ...validFiles].slice(0, maxFiles);
        onCVsSelected?.(mergedFiles);
        return;
      }

      const validOffer = selectedFiles.find((file) => isAcceptedFile(file, OFFER_ACCEPT));
      if (validOffer) {
        onOfferSelected?.(validOffer);
      }
    },
    [cvFiles, maxFiles, onCVsSelected, onOfferSelected]
  );

  const handleDrop = useCallback(
    (event: React.DragEvent, target: UploadTarget) => {
      event.preventDefault();
      event.stopPropagation();
      setActiveTarget(null);
      handleFiles(target, Array.from(event.dataTransfer.files));
    },
    [handleFiles]
  );

  const renderSelectedCVs = () => {
    if (mode !== 'combined' || cvFiles.length === 0) {
      return null;
    }

    return (
      <div className="space-y-3">
        {cvFiles.map((file, index) => (
          <motion.div
            key={`${file.name}-${index}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`${PANEL_STYLES} flex items-center justify-between gap-4`}
          >
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-300">
                <FileText className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-slate-400">{'CV pr\u00eat pour le traitement'}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onRemoveCV?.(index)}
              disabled={isLoading}
              className="rounded-full p-2 text-slate-400 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              aria-label={`Retirer ${file.name}`}
            >
              <X className="h-4 w-4" />
            </button>
          </motion.div>
        ))}
      </div>
    );
  };

  const renderSelectedOffer = () => {
    if (!offerFile) {
      return null;
    }

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`${PANEL_STYLES} flex items-center justify-between gap-4`}
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-300">
            <FileText className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">{offerFile.name}</p>
            <p className="text-xs text-slate-400">{'Offre pr\u00eate pour le traitement'}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRemoveOffer}
          disabled={isLoading}
          className="rounded-full p-2 text-slate-400 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Retirer l'offre"
        >
          <X className="h-4 w-4" />
        </button>
      </motion.div>
    );
  };

  return (
    <div className={mode === 'combined' ? 'grid gap-6 lg:grid-cols-2' : 'space-y-12'}>
      {dropzones.map((dropzone) => {
        const isActive = activeTarget === dropzone.target;

        return (
          <div key={dropzone.target} className="space-y-4">
            <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-white">
              {dropzone.title}
            </h2>

            <motion.div
              whileHover={{ y: -2 }}
              className={`${DROPZONE_STYLES.base} ${isActive ? DROPZONE_STYLES.active : DROPZONE_STYLES.idle}`}
              onDragEnter={(event) => handleDragState(event, dropzone.target)}
              onDragLeave={(event) => handleDragState(event, null)}
              onDragOver={(event) => handleDragState(event, dropzone.target)}
              onDrop={(event) => handleDrop(event, dropzone.target)}
            >
              <label className="flex w-full cursor-pointer flex-col items-center gap-3 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-full border border-cyan-400/25 bg-cyan-400/8 text-cyan-300">
                  <Upload className="h-7 w-7" />
                </span>

                <div className="space-y-2">
                  <p className="text-[16px] font-semibold tracking-[-0.02em] text-white">
                    {dropzone.description}
                  </p>
                  <p className={`text-sm ${dropzone.accentClassName}`}>{dropzone.formats}</p>
                </div>

                <input
                  type="file"
                  accept={dropzone.accept}
                  multiple={dropzone.multiple}
                  disabled={isLoading}
                  className="hidden"
                  onChange={(event) => handleFiles(dropzone.target, Array.from(event.target.files || []))}
                />
              </label>
            </motion.div>

            {dropzone.target === 'cv' ? renderSelectedCVs() : renderSelectedOffer()}
          </div>
        );
      })}
    </div>
  );
}
