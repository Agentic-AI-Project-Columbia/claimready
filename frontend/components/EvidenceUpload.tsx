'use client';

import { Upload, FileText, Image as ImageIcon, Mail, X } from 'lucide-react';
import { useCallback, useState } from 'react';
import clsx from 'clsx';

export interface PreviewFile {
  file: File;
  id: string;
}

interface Props {
  files: PreviewFile[];
  onChange: (files: PreviewFile[]) => void;
}

const iconFor = (name: string) => {
  const lower = name.toLowerCase();
  if (/\.(png|jpe?g|gif|webp|heic)$/.test(lower)) return ImageIcon;
  if (/\.eml$/.test(lower)) return Mail;
  return FileText;
};

export const SAMPLE_DRAG_MIME = 'application/x-claimready-sample';

export function EvidenceUpload({ files, onChange }: Props) {
  const [isOver, setOver] = useState(false);

  const ingest = useCallback(
    (list: FileList | File[]) => {
      const next = Array.from(list).map((f) => ({
        file: f,
        id: `${f.name}-${f.size}-${f.lastModified}`,
      }));
      // dedupe
      const seen = new Set(files.map((f) => f.id));
      const merged = [...files, ...next.filter((n) => !seen.has(n.id))];
      onChange(merged);
    },
    [files, onChange],
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setOver(false);

      const sampleNames = e.dataTransfer.getData(SAMPLE_DRAG_MIME);
      if (sampleNames) {
        const list = sampleNames.split('\n').map((s) => s.trim()).filter(Boolean);
        const fetched = await Promise.all(
          list.map(async (name) => {
            const r = await fetch(`/sample-evidence/${name}`);
            if (!r.ok) throw new Error(`could not fetch ${name}`);
            const blob = await r.blob();
            const mime = blob.type || (name.endsWith('.eml') ? 'message/rfc822' : 'text/plain');
            return new File([blob], name, { type: mime, lastModified: Date.now() });
          }),
        );
        if (fetched.length) ingest(fetched);
        return;
      }

      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        ingest(e.dataTransfer.files);
      }
    },
    [ingest],
  );

  return (
    <div className="space-y-5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={handleDrop}
        className={clsx(
          'rounded-2xl border-2 border-dashed p-10 text-center transition',
          isOver
            ? 'border-sage-700 bg-sage-50'
            : 'border-ink-200 hover:border-sage-400 bg-ink-50/40',
        )}
      >
        <Upload className="mx-auto mb-3 text-sage-600" size={28} />
        <p className="font-serif text-lg text-ink-900">Drop your evidence here</p>
        <p className="text-sm text-ink-300 mt-1 mb-4">
          Contracts (PDF), emails (.eml), invoices, screenshots — anything the
          court should see.
        </p>
        <label className="inline-block cursor-pointer">
          <input
            type="file"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && ingest(e.target.files)}
          />
          <span className="px-5 py-2.5 bg-white border border-ink-200 rounded-lg text-sm font-medium text-sage-700 hover:border-sage-400 transition">
            Browse files
          </span>
        </label>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((pf) => {
            const Icon = iconFor(pf.file.name);
            return (
              <li
                key={pf.id}
                className="flex items-center gap-3 bg-white border border-ink-200 rounded-xl px-4 py-3 shadow-sink"
              >
                <Icon size={18} className="text-sage-600 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-ink-900 truncate">{pf.file.name}</p>
                  <p className="text-xs text-ink-300">
                    {(pf.file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
                <button
                  onClick={() => onChange(files.filter((f) => f.id !== pf.id))}
                  className="p-1.5 rounded-md hover:bg-ink-100 text-ink-300 hover:text-ink-900 transition"
                  aria-label="Remove file"
                >
                  <X size={16} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
