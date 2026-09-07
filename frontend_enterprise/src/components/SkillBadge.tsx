'use client';

import React from 'react';
import { skillCategoryClass, type StructuredSkill } from '@/lib/skillUtils';

interface Props {
  skill: StructuredSkill;
}

export function SkillBadge({ skill }: Props) {
  return (
    <span
      className={`text-xs border px-2.5 py-1 rounded-full ${skillCategoryClass(skill.category)}`}
    >
      {skill.name}
    </span>
  );
}
