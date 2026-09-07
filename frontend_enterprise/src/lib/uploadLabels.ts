// French labels for CV routing metadata, sourced from the backend's own
// reference data (service/migrations/009_ref_tables.sql: ref.profiles.label_fr /
// ref.seniorities.label_fr) so the upload screen speaks the same language as
// the Vivier page that displays the result of this exact data.
export const PROFILE_LABELS_FR: Record<string, string> = {
  FullStack: 'Développeur Full Stack',
  DevOps: 'Ingénieur DevOps',
  Data: 'Data Engineer / Scientist',
  BusinessAnalyst: 'Business Analyst / MOA',
  HR: 'Ressources Humaines',
  Project_Manager: 'Chef de Projet',
  Testeur: 'Ingénieur QA / Test',
  Cybersecurity: 'Expert Cybersécurité',
  Mobile: 'Développeur Mobile',
  Frontend: 'Développeur Frontend',
  Backend: 'Développeur Backend',
  Cloud: 'Architecte Cloud',
  ERP: 'Consultant ERP',
};

const SENIORITY_LABELS_FR: Record<string, string> = {
  junior: 'Junior',
  confirme: 'Confirmé',
  senior: 'Senior',
  expert: 'Expert',
};

/** Falls back to a de-slugged version of unknown codes (e.g. a newly created profile folder). */
export function profileLabelFr(code: string): string {
  return PROFILE_LABELS_FR[code] ?? code.replace(/_/g, ' ');
}

export function seniorityLabelFr(code: string): string {
  return SENIORITY_LABELS_FR[code.toLowerCase()] ?? code;
}

/** Plain-language fallback for an HTTP failure with no usable `detail` from the API. */
export function friendlyHttpError(status: number): string {
  if (status >= 500) return "Le serveur est momentanément indisponible. Réessayez dans un instant.";
  if (status === 413) return "Fichier trop volumineux.";
  if (status === 401 || status === 403) return "Session expirée — reconnectez-vous.";
  return `Erreur inattendue (code ${status}).`;
}
