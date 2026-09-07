export interface StructuredSkill {
  id?: number | string;
  name: string;
  category?: string | null;
  level?: string | null;
}

export type SkillLike = string | StructuredSkill;

export function isStructuredSkill(skill: SkillLike): skill is StructuredSkill {
  return typeof skill === 'object' && skill !== null && typeof skill.name === 'string';
}

export function skillDisplayName(skill: SkillLike): string {
  if (typeof skill === 'string') return skill;
  if (isStructuredSkill(skill)) return skill.name;
  return String(skill);
}

export function skillKey(skill: SkillLike, index: number): string {
  if (typeof skill === 'string') return skill;
  if (isStructuredSkill(skill)) {
    const id = skill.id != null ? String(skill.id) : '';
    return id ? `${id}-${skill.name}` : `${skill.name}-${index}`;
  }
  return String(index);
}

const CATEGORY_CLASSES: Record<string, string> = {
  language: 'text-blue-300 bg-blue-400/10 border-blue-400/20',
  framework: 'text-teal-300 bg-teal-400/10 border-teal-400/20',
  tool: 'text-slate-300 bg-slate-400/10 border-slate-400/20',
  methodology: 'text-purple-300 bg-purple-400/10 border-purple-400/20',
  cloud: 'text-cyan-300 bg-cyan-400/10 border-cyan-400/20',
  database: 'text-amber-300 bg-amber-400/10 border-amber-400/20',
};

const DEFAULT_CLASS = 'text-slate-300 bg-slate-500/10 border-slate-500/20';

export function skillCategoryClass(category?: string | null): string {
  const key = (category || 'other').toLowerCase();
  return CATEGORY_CLASSES[key] ?? DEFAULT_CLASS;
}

export function formatSkillOverlap(matching: number, total: number): string | null {
  if (!total || total <= 0) return null;
  return `${matching}/${total} compétences requises maîtrisées`;
}
