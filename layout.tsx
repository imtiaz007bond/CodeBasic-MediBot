import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'MediBot | MediAssist', description: 'Secure internal knowledge assistant' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
