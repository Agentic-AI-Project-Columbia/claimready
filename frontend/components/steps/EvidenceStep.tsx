'use client';

import { StepShell } from '@/components/StepShell';
import { EvidenceUpload, type PreviewFile } from '@/components/EvidenceUpload';

export function EvidenceStep({
  files,
  setFiles,
  onBack,
  onNext,
  totalSteps,
}: {
  files: PreviewFile[];
  setFiles: (f: PreviewFile[]) => void;
  onBack: () => void;
  onNext: () => void;
  totalSteps: number;
}) {
  return (
    <StepShell
      step={6}
      totalSteps={totalSteps}
      kicker="Step 6 of 8"
      title="Show us your evidence."
      helpText={
        <>
          The agent reads everything you upload — contracts, invoices,
          email threads, screenshots — and pulls the facts that support
          your claim. The more you give it, the stronger your packet.
          Originals stay on your machine; we only use the extracted text.
        </>
      }
      onBack={onBack}
      onNext={onNext}
    >
      <EvidenceUpload files={files} onChange={setFiles} />
    </StepShell>
  );
}
