// Root path is handled by middleware.ts:
//   unauthenticated → /login
//   authenticated   → /recruiter or /sourcer
// This page is a fallback only (should never be reached in normal flow).
import { redirect } from 'next/navigation';

export default function RootPage() {
  redirect('/login');
}
