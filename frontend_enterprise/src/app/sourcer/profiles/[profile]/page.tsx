'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

export default function SourcerProfileRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/sourcer/candidates');
  }, [router]);

  return (
    <div className="flex justify-center h-48">
      <Loader2 className="h-8 w-8 animate-spin text-[#1f9d94] mt-16" />
    </div>
  );
}
