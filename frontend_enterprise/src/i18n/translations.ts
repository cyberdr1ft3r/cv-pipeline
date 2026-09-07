// French translations for the application
export const fr = {
  // Navigation
  nav: {
    home: "Accueil",
    pipeline: "Pipeline",
    results: "Résultats",
    signIn: "Se connecter",
    getStarted: "Commencer",
  },

  // Hero Section
  hero: {
    poweredBy: "Alimenté par la technologie IA avancée",
    title: "Découverte intelligente de talents pour les équipes de recrutement modernes",
    description:
      "Transformez votre processus de recrutement avec l'analyse instantanée de CV par IA et l'appariement intelligent des candidats...",
    startTrial: "Commencer l'essai gratuit",
    requestDemo: "Demander une démo",
    socCertified: "Certifié SOC 2",
    gdprCompliant: "Conforme au RGPD",
    enterpriseReady: "Prêt pour l'entreprise",
  },

  // Pipeline Pages
  pipeline: {
    title: "Pipeline de recrutement",
    uploadTitle: "Téléchargez vos fichiers",
    uploadDescription: "Fournissez des CV et une offre d'emploi pour commencer l'appariement",
    selectMode: "Sélectionnez un mode",
    uploadCVsOffer: "Télécharger les CV + Offre",
    offerOnly: "Offre uniquement",
    archive: "Archiver les résultats après traitement (recommandé pour les sauvegardes)",
    cvs: "CV",
    jobOffer: "Offre d'emploi",
    totalSize: "Taille totale",
    startProcessing: "Démarrer le traitement",
    processing: "Traitement en cours...",
    uploadCVs: "Télécharger les CV des candidats",
    uploadJobOffer: "Télécharger l'offre d'emploi",
    dragDropFiles: "Déposez les fichiers ici ou cliquez pour télécharger",
    supportedFormats: "Formats supportés: PDF, DOC, DOCX, TXT",
  },

  // Progress Tracker
  progress: {
    overallProgress: "Progression générale",
    extraction: "Extraction",
    matching: "Appariement",
    formatting: "Formatage",
    complete: "Terminé",
  },

  // Results Page
  results: {
    title: "Résultats",
    finalResults: "Résultats finaux",
    matchingResults: "Résultats d'appariement",
    downloadFormattedCVs: "Télécharger les CV formatés",
    downloadMatchingResults: "Télécharger les résultats d'appariement",
    downloadArchive: "Télécharger l'archive",
    noResults: "Aucun résultat disponible",
    failedFetch: "Échec de la récupération des résultats:",
    runFinalScoring: "Exécuter le scoring final",
    uploadScores: "Télécharger les scores",
  },

  // Dashboard
  dashboard: {
    title: "Tableau de bord du recruteur",
    subtitle: "Centre de commande des recruteurs",
    description:
      "Optimisez vos processus. Téléchargez vos descriptions de postes et recevez instantanément les correspondances de candidats classées par IA...",
    matchingPrecision: "Précision d'appariement",
    averageMatchingTime: "Temps d'appariement moyen",
    timeSaved: "Temps économisé",
    candidatesAnalyzed: "Candidats analysés par jour",
  },

  // Status Messages
  status: {
    success: "Succès",
    error: "Erreur",
    loading: "Chargement...",
    processing: "Traitement en cours...",
    completed: "Terminé",
    failed: "Échoué",
    pending: "En attente",
  },

  // Error Messages
  errors: {
    fileUploadFailed: "Le téléchargement du fichier a échoué",
    invalidFileType: "Type de fichier invalide",
    fileTooLarge: "Le fichier est trop volumineux",
    noFilesSelected: "Aucun fichier sélectionné",
    apiError: "Erreur du serveur",
    networkError: "Erreur réseau",
    jobNotFound: "Travail non trouvé",
    resultsNotFound: "Résultats non trouvés",
  },

  // Buttons
  buttons: {
    upload: "Télécharger",
    submit: "Soumettre",
    cancel: "Annuler",
    retry: "Réessayer",
    download: "Télécharger",
    refresh: "Actualiser",
    close: "Fermer",
    save: "Enregistrer",
    delete: "Supprimer",
    edit: "Modifier",
    back: "Retour",
    next: "Suivant",
    previous: "Précédent",
  },

  // Footer
  footer: {
    copyright: "© 2026 CV-Tech. Tous droits réservés.",
    tagline: "Découverte intelligente de talents alimentée par la technologie IA avancée.",
    product: "Produit",
    company: "Entreprise",
    legal: "Juridique",
    resources: "Ressources",
    privacyPolicy: "Politique de confidentialité",
    termsOfService: "Conditions d'utilisation",
    gdprCompliance: "Conformité RGPD",
    contact: "Contact",
  },

  // Table Headers
  table: {
    candidateName: "Nom du candidat",
    score: "Score",
    matchPercentage: "Pourcentage de correspondance",
    overallScore: "Score global",
    testScore: "Score du test",
    finalScore: "Score final",
    rank: "Classement",
    email: "Email",
    experience: "Expérience",
    technologies: "Technologies",
    actions: "Actions",
  },
};

export type Translations = typeof fr;
