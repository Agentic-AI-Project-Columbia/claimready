import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ClaimReady — Small Claims, Filed Right',
  description:
    'Stop writing off unpaid invoices. Generate a court-ready NYC small-claims packet in minutes.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen relative">
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
