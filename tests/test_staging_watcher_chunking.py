from __future__ import annotations

import copy
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from script import staging_watcher as watcher
from script.chunked_extraction import (
    ChunkingError,
    ExtractionQualityError,
    chunk_cv_text,
    merge_chunk_results,
    validate_extraction_quality,
)
from service.cv_storage import LocalCVStorage


def _empty_chunk() -> dict:
    return {
        "informations_personnelles": {},
        "profil_resume": {
            "description": "",
            "annees_experience": "",
            "specialisations": [],
        },
        "formation": [],
        "certifications": [],
        "competences": {
            "methodologies_et_outils": [],
            "technologies": [],
        },
        "projets_realises": [],
        "langues": [],
        "experiences_professionnelles": [],
    }


def _experience(
    title: str,
    company: str,
    dates: str,
    **overrides,
) -> dict:
    result = {
        "titre_poste": title,
        "type_contrat": "CDI",
        "entreprise": company,
        "secteur": "",
        "lieu": "",
        "dates": dates,
        "duree": "",
        "contexte": "",
        "missions": [],
        "realisations": [],
        "environnement_technique": [],
        "methodologies": [],
        "management": "",
    }
    result.update(overrides)
    return result


def _llm_response(content: str, finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]
    )


class ChunkerTests(unittest.TestCase):
    def test_short_text_is_one_chunk(self) -> None:
        self.assertEqual(
            chunk_cv_text("Short CV paragraph."),
            ["Short CV paragraph."],
        )

    def test_long_single_paragraph_splits_without_losing_markers(self) -> None:
        markers = [f"WORD{i:03d}" for i in range(80)]
        chunks = chunk_cv_text(
            " ".join(markers),
            chunk_chars=100,
            overlap_chars=15,
            max_chunks=20,
        )

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))
        for marker in markers:
            self.assertTrue(any(marker in chunk for chunk in chunks), marker)

    def test_paragraph_boundaries_are_preferred(self) -> None:
        first = "FIRST " * 12
        second = "SECOND " * 12
        chunks = chunk_cv_text(
            first.strip() + "\n\n" + second.strip(),
            chunk_chars=100,
            overlap_chars=10,
        )

        self.assertEqual(chunks[0], first.strip())

    def test_adjacent_chunks_overlap(self) -> None:
        chunks = chunk_cv_text(
            " ".join(f"token{i}" for i in range(100)),
            chunk_chars=120,
            overlap_chars=30,
        )

        for left, right in zip(chunks, chunks[1:]):
            self.assertTrue(set(left.split()) & set(right.split()))

    def test_output_is_deterministic_and_covers_every_source_section(self) -> None:
        sections = [
            f"SECTION-{index} " + ("detail " * 20)
            for index in range(12)
        ]
        text = "\n\n".join(sections)
        first = chunk_cv_text(text, chunk_chars=180, overlap_chars=25)
        second = chunk_cv_text(text, chunk_chars=180, overlap_chars=25)

        self.assertEqual(first, second)
        for index in range(12):
            marker = f"SECTION-{index}"
            self.assertTrue(any(marker in chunk for chunk in first), marker)

    def test_max_chunks_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(ChunkingError, "max_chunks=2"):
            chunk_cv_text(
                "word " * 200,
                chunk_chars=100,
                overlap_chars=20,
                max_chunks=2,
            )

    def test_extreme_overlap_and_unbroken_text_still_terminate(self) -> None:
        chunks = chunk_cv_text(
            "x" * 60,
            chunk_chars=20,
            overlap_chars=19,
            max_chunks=100,
        )

        self.assertLessEqual(len(chunks), 60)
        self.assertTrue(all(0 < len(chunk) <= 20 for chunk in chunks))
        self.assertEqual(chunks[0], "x" * 20)
        self.assertEqual(chunks[-1][-1], "x")


class MergeTests(unittest.TestCase):
    def test_duplicate_overlap_experience_merges_once(self) -> None:
        first = _empty_chunk()
        first["experiences_professionnelles"] = [
            _experience(
                "Développeur confirmé",
                "Société Exemple",
                "2020 - 2022",
                contexte="Migration métier",
                missions=["Développer API"],
                environnement_technique=["Python"],
            )
        ]
        second = _empty_chunk()
        second["experiences_professionnelles"] = [
            _experience(
                "developpeur confirme",
                "SOCIETE EXEMPLE",
                "2020–2022",
                contexte="",
                missions=["Développer API", "Automatiser les tests"],
                environnement_technique=["python", "PostgreSQL"],
            )
        ]

        merged = merge_chunk_results([first, second])
        experiences = merged["experiences_professionnelles"]

        self.assertEqual(len(experiences), 1)
        self.assertEqual(experiences[0]["titre_poste"], "Développeur confirmé")
        self.assertEqual(experiences[0]["contexte"], "Migration métier")
        self.assertEqual(
            experiences[0]["missions"],
            ["Développer API", "Automatiser les tests"],
        )
        self.assertEqual(
            experiences[0]["environnement_technique"],
            ["Python", "PostgreSQL"],
        )

    def test_different_jobs_at_same_company_stay_separate(self) -> None:
        chunk = _empty_chunk()
        chunk["experiences_professionnelles"] = [
            _experience("Développeur", "Exemple SA", "2018 - 2020"),
            _experience("Tech Lead", "Exemple SA", "2021 - 2023"),
        ]

        merged = merge_chunk_results([chunk])

        self.assertEqual(len(merged["experiences_professionnelles"]), 2)

    def test_same_title_at_different_companies_stays_separate(self) -> None:
        first = _empty_chunk()
        first["experiences_professionnelles"] = [
            _experience("Consultant", "Alpha", "2020 - 2021")
        ]
        second = _empty_chunk()
        second["experiences_professionnelles"] = [
            _experience("Consultant", "Beta", "2020 - 2021")
        ]

        merged = merge_chunk_results([first, second])

        self.assertEqual(len(merged["experiences_professionnelles"]), 2)

    def test_ambiguous_repeated_role_fragment_stays_separate(self) -> None:
        first = _empty_chunk()
        first["experiences_professionnelles"] = [
            _experience("Engineer", "Alpha", "2018 - 2019"),
            _experience("Engineer", "Alpha", "2022 - 2023"),
        ]
        second = _empty_chunk()
        second["experiences_professionnelles"] = [
            _experience("Engineer", "Alpha", "")
        ]

        merged = merge_chunk_results([first, second])

        self.assertEqual(len(merged["experiences_professionnelles"]), 3)

    def test_projects_merge_only_with_conservative_identity(self) -> None:
        first = _empty_chunk()
        first["projets_realises"] = [
            {
                "nom": "Portail Client",
                "client_ou_contexte": "Alpha",
                "periode": "",
                "description": "Version initiale",
                "technologies": ["React"],
            },
            {"nom": "", "technologies": ["Python"]},
        ]
        second = _empty_chunk()
        second["projets_realises"] = [
            {
                "nom": "portail-client",
                "client_ou_contexte": "ALPHA",
                "periode": "",
                "description": "",
                "technologies": ["react", "FastAPI"],
            },
            {"nom": "", "technologies": ["Python"]},
        ]

        merged = merge_chunk_results([first, second])

        self.assertEqual(len(merged["projets_realises"]), 3)
        project = merged["projets_realises"][0]
        self.assertEqual(project["description"], "Version initiale")
        self.assertEqual(project["technologies"], ["React", "FastAPI"])

    def test_languages_formations_and_certifications_dedupe(self) -> None:
        first = _empty_chunk()
        first["langues"] = [
            {"nom": "Anglais", "niveau": "C1", "certifications": ""}
        ]
        first["formation"] = [
            {
                "institution": "Université Exemple",
                "diplome": "Master Informatique",
                "dates": "2018 - 2020",
                "mention": "",
            }
        ]
        first["certifications"] = [
            {
                "nom": "Cloud Practitioner",
                "organisme": "AWS",
                "date": "",
                "niveau": "",
            }
        ]
        second = _empty_chunk()
        second["langues"] = [
            {"nom": "anglais", "niveau": "", "certifications": "TOEIC"}
        ]
        second["formation"] = [
            {
                "institution": "universite exemple",
                "diplome": "MASTER INFORMATIQUE",
                "dates": "2018-2020",
                "mention": "Bien",
            }
        ]
        second["certifications"] = [
            {
                "nom": "cloud practitioner",
                "organisme": "aws",
                "date": "2023",
                "niveau": "Foundational",
            }
        ]

        merged = merge_chunk_results([first, second])

        self.assertEqual(len(merged["langues"]), 1)
        self.assertEqual(merged["langues"][0]["niveau"], "C1")
        self.assertEqual(merged["langues"][0]["certifications"], "TOEIC")
        self.assertEqual(len(merged["formation"]), 1)
        self.assertEqual(merged["formation"][0]["mention"], "Bien")
        self.assertEqual(len(merged["certifications"]), 1)
        self.assertEqual(merged["certifications"][0]["date"], "2023")

    def test_skill_union_is_stable_and_blanks_never_overwrite(self) -> None:
        first = _empty_chunk()
        first["informations_personnelles"] = {
            "nom_complet": "Candidate SYNTHETIQUE",
            "titre": "Data Engineer confirmé",
        }
        first["competences"] = {
            "technologies": ["Python", "PostgreSQL"],
            "methodologies_et_outils": ["Scrum", "Git"],
        }
        second = _empty_chunk()
        second["informations_personnelles"] = {
            "nom_complet": "",
            "titre": "",
            "email": "candidate@example.test",
        }
        second["competences"] = {
            "technologies": ["python", "Kafka"],
            "methodologies_et_outils": ["git", "Kanban"],
        }

        merged = merge_chunk_results([first, second])

        self.assertEqual(
            merged["informations_personnelles"]["nom_complet"],
            "Candidate SYNTHETIQUE",
        )
        self.assertEqual(
            merged["informations_personnelles"]["email"],
            "candidate@example.test",
        )
        self.assertEqual(
            merged["competences"]["technologies"],
            ["Python", "PostgreSQL", "Kafka"],
        )
        self.assertEqual(
            merged["competences"]["methodologies_et_outils"],
            ["Scrum", "Git", "Kanban"],
        )

    def test_punctuation_significant_skills_remain_distinct(self) -> None:
        chunk = _empty_chunk()
        chunk["competences"]["technologies"] = ["C++", "C#", "c++"]

        merged = merge_chunk_results([chunk])

        self.assertEqual(
            merged["competences"]["technologies"],
            ["C++", "C#"],
        )


class QualityGateTests(unittest.TestCase):
    def _valid_junior(self) -> dict:
        result = _empty_chunk()
        result["informations_personnelles"] = {
            "nom_complet": "Junior SYNTHETIQUE"
        }
        result["formation"] = [
            {"institution": "École Exemple", "diplome": "Licence"}
        ]
        result["competences"]["technologies"] = ["Python"]
        return result

    def test_missing_name_is_rejected(self) -> None:
        result = self._valid_junior()
        result["informations_personnelles"]["nom_complet"] = ""

        with self.assertRaisesRegex(ExtractionQualityError, "name"):
            validate_extraction_quality("Formation", result)

    def test_experience_section_without_experiences_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionQualityError, "experience section"):
            validate_extraction_quality(
                "EXPÉRIENCES PROFESSIONNELLES\nConsultant",
                self._valid_junior(),
            )

    def test_junior_without_experience_signal_is_allowed(self) -> None:
        validate_extraction_quality(
            "FORMATION\nLicence\nCOMPÉTENCES\nPython",
            self._valid_junior(),
        )

    def test_user_experience_phrase_is_not_an_employment_heading(self) -> None:
        validate_extraction_quality(
            "FORMATION\nMaster en User Experience et design",
            self._valid_junior(),
        )

    def test_structurally_empty_result_is_rejected(self) -> None:
        result = _empty_chunk()
        result["informations_personnelles"] = {
            "nom_complet": "Candidate SYNTHETIQUE"
        }

        with self.assertRaisesRegex(ExtractionQualityError, "structurally empty"):
            validate_extraction_quality("Profil personnel", result)

    def test_unknown_record_shell_is_structurally_empty(self) -> None:
        result = _empty_chunk()
        result["informations_personnelles"] = {
            "nom_complet": "Candidate SYNTHETIQUE"
        }
        result["experiences_professionnelles"] = [{"unknown": "value"}]

        with self.assertRaisesRegex(ExtractionQualityError, "structurally empty"):
            validate_extraction_quality("Profil personnel", result)


class OrchestrationTests(unittest.TestCase):
    def test_every_chunk_succeeds_before_deterministic_merge(self) -> None:
        first = _empty_chunk()
        first["informations_personnelles"] = {"nom_complet": "Test PERSON"}
        second = _empty_chunk()
        second["competences"]["technologies"] = ["Python"]

        with patch.object(
            watcher,
            "chunk_cv_text",
            return_value=["chunk one", "chunk two"],
        ), patch.object(
            watcher,
            "_extract_chunk_json",
            side_effect=[first, second],
        ) as extract_chunk:
            merged = watcher._extract_cv_json("source", "synthetic.pdf")

        self.assertEqual(
            extract_chunk.call_args_list,
            [call("chunk one", 1, 2), call("chunk two", 2, 2)],
        )
        self.assertEqual(
            merged["informations_personnelles"]["nom_complet"],
            "Test PERSON",
        )
        self.assertEqual(merged["competences"]["technologies"], ["Python"])

    def test_middle_chunk_failure_prevents_merge(self) -> None:
        with patch.object(
            watcher,
            "chunk_cv_text",
            return_value=["one", "two", "three"],
        ), patch.object(
            watcher,
            "_extract_chunk_json",
            side_effect=[_empty_chunk(), RuntimeError("chunk failed")],
        ), patch.object(watcher, "merge_chunk_results") as merge:
            with self.assertRaisesRegex(RuntimeError, "chunk failed"):
                watcher._extract_cv_json("source")

        merge.assert_not_called()

    def test_length_chunk_never_reaches_parser_or_merge(self) -> None:
        valid = '{"informations_personnelles": {}}'
        truncated = '{"experiences_professionnelles": ['
        responses = [
            _llm_response(valid),
            _llm_response(truncated, "length"),
        ]
        with patch.dict(
            watcher._CONFIG["api"],
            {"max_retries": 1, "retry_wait_seconds": 0},
        ), patch.object(
            watcher,
            "chunk_cv_text",
            return_value=["one", "two"],
        ), patch.object(
            watcher._llm_client.chat.completions,
            "create",
            side_effect=responses,
        ), patch.object(
            watcher,
            "merge_chunk_results",
        ) as merge, patch.object(
            watcher,
            "_parse_llm_json",
            wraps=watcher._parse_llm_json,
        ) as parse:
            with self.assertRaisesRegex(RuntimeError, "chunk 2/2"):
                watcher._extract_cv_json("source")

        self.assertEqual(
            parse.call_args_list,
            [call(valid, allow_truncated_repair=False)],
        )
        merge.assert_not_called()

    def test_non_length_malformed_json_uses_one_strict_repair(self) -> None:
        malformed = '{"informations_personnelles": {"nom_complet": "Test"}'
        repaired = '{"informations_personnelles": {"nom_complet": "Test"}}'
        with patch.object(
            watcher,
            "_call_llm",
            side_effect=[malformed, repaired],
        ) as call_llm:
            result = watcher._extract_chunk_json("chunk", 1, 1)

        self.assertEqual(
            result["informations_personnelles"]["nom_complet"],
            "Test",
        )
        self.assertEqual(call_llm.call_count, 2)
        self.assertTrue(
            call_llm.call_args_list[0].kwargs["reject_truncated"]
        )
        self.assertFalse(
            call_llm.call_args_list[1].kwargs["use_fallback"]
        )
        self.assertTrue(
            call_llm.call_args_list[1].kwargs["reject_truncated"]
        )

    def test_merged_experiences_are_enriched_once_after_merge(self) -> None:
        chunk = _empty_chunk()
        chunk["profil_resume"]["annees_experience"] = "99 ans"
        chunk["experiences_professionnelles"] = [
            _experience("Engineer", "Alpha", "Jan 2020 - Dec 2022")
        ]
        merged = merge_chunk_results([chunk])

        with patch.object(
            watcher,
            "enrich_annees_experience",
            wraps=watcher.enrich_annees_experience,
        ) as enrich:
            normalized = watcher._validate_json(merged)

        enrich.assert_called_once_with(merged)
        self.assertEqual(
            normalized["profil_resume"]["annees_experience"],
            "3 ans",
        )

    def test_quality_gate_runs_before_classification(self) -> None:
        result = _empty_chunk()
        result["informations_personnelles"] = {"nom_complet": "Test PERSON"}
        result["formation"] = [{"institution": "School"}]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            source = staging / "candidate.docx"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"docx")
            storage = LocalCVStorage(
                storage_root=root,
                library_root=root / "CV_Theque",
                staging_path=staging,
            )
            staged = watcher.StagedFile(str(source), source.name, None, None)
            sequence = MagicMock()
            quality = MagicMock()
            classify = MagicMock(
                side_effect=watcher.ClassificationError("stop after ordering")
            )
            sequence.attach_mock(quality, "quality")
            sequence.attach_mock(classify, "classify")

            with patch.object(
                watcher,
                "WATCHER_STAGING_PATH",
                str(staging),
            ), patch.object(
                watcher,
                "_extract_text_docx",
                return_value="education and skills " * 10,
            ), patch.object(
                watcher,
                "_extract_cv_json",
                return_value=copy.deepcopy(result),
            ), patch.object(
                watcher,
                "_validate_json",
                side_effect=lambda value: value,
            ), patch.object(
                watcher,
                "validate_extraction_quality",
                quality,
            ), patch.object(watcher, "_classify", classify):
                watcher.CVProcessor(storage).process(
                    staged,
                    known_profiles=frozenset(),
                    pending_profiles={},
                    pending_lock=threading.Lock(),
                )

        self.assertEqual(
            [entry[0] for entry in sequence.mock_calls],
            ["quality", "classify"],
        )

    def test_middle_chunk_failure_persists_no_partial_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            source = staging / "long.docx"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"original")
            storage = LocalCVStorage(
                storage_root=root,
                library_root=root / "CV_Theque",
                staging_path=staging,
            )
            staged = watcher.StagedFile(str(source), source.name, None, None)

            with patch.object(
                watcher,
                "WATCHER_STAGING_PATH",
                str(staging),
            ), patch.object(
                watcher,
                "_extract_text_docx",
                return_value="long CV text " * 20,
            ), patch.object(
                watcher,
                "chunk_cv_text",
                return_value=["one", "two", "three"],
            ), patch.object(
                watcher,
                "_extract_chunk_json",
                side_effect=[_empty_chunk(), RuntimeError("middle failed")],
            ), patch.object(
                storage,
                "store_extracted",
                wraps=storage.store_extracted,
            ) as store_extracted, patch.object(
                storage,
                "store_original",
                wraps=storage.store_original,
            ) as store_original, patch.object(
                watcher,
                "_classify",
            ) as classify:
                watcher.CVProcessor(storage).process(
                    staged,
                    known_profiles=frozenset(),
                    pending_profiles={},
                    pending_lock=threading.Lock(),
                )

            self.assertTrue((staging / "failed" / source.name).exists())
            store_extracted.assert_not_called()
            store_original.assert_not_called()
            classify.assert_not_called()


class SyntheticLongCvRegressionTests(unittest.TestCase):
    def test_long_cv_preserves_distinct_records_without_overlap_duplicates(
        self,
    ) -> None:
        sections = [
            "Candidate SYNTHETIQUE\nData Engineer confirmé",
            "EXPÉRIENCES PROFESSIONNELLES",
            "EXP-ALPHA Développeur Alpha Jan 2018 - Dec 2019",
            "filler " * 60,
            "EXP-BETA Data Engineer Beta Jan 2020 - Dec 2021",
            "filler " * 60,
            "EXP-GAMMA Tech Lead Gamma Jan 2022 - Dec 2023",
            "PROJET-ATLAS Portail analytique Client Exemple",
            "FORMATION-MASTER Université Exemple 2016 - 2018",
            "CERT-CLOUD Organisme Exemple 2023",
            "LANG-FR Français natif\nLANG-EN Anglais C1",
            "Python PostgreSQL Kafka Scrum Git",
        ]
        source = "\n\n".join(sections)

        def extraction_for_chunk(
            chunk_text: str,
            _index: int,
            _total: int,
        ) -> dict:
            result = _empty_chunk()
            if "Candidate SYNTHETIQUE" in chunk_text:
                result["informations_personnelles"] = {
                    "nom_complet": "Candidate SYNTHETIQUE",
                    "titre": "Data Engineer confirmé",
                }
            experience_specs = (
                ("EXP-ALPHA", "Développeur", "Alpha", "Jan 2018 - Dec 2019"),
                ("EXP-BETA", "Data Engineer", "Beta", "Jan 2020 - Dec 2021"),
                ("EXP-GAMMA", "Tech Lead", "Gamma", "Jan 2022 - Dec 2023"),
            )
            for marker, title, company, dates in experience_specs:
                if marker in chunk_text:
                    result["experiences_professionnelles"].append(
                        _experience(
                            title,
                            company,
                            dates,
                            missions=[f"Mission {marker}"],
                        )
                    )
            if "PROJET-ATLAS" in chunk_text:
                result["projets_realises"].append(
                    {
                        "nom": "Atlas",
                        "client_ou_contexte": "Client Exemple",
                        "periode": "2023",
                        "technologies": ["Python"],
                    }
                )
            if "FORMATION-MASTER" in chunk_text:
                result["formation"].append(
                    {
                        "institution": "Université Exemple",
                        "diplome": "Master",
                        "dates": "2016 - 2018",
                    }
                )
            if "CERT-CLOUD" in chunk_text:
                result["certifications"].append(
                    {
                        "nom": "Cloud",
                        "organisme": "Organisme Exemple",
                        "date": "2023",
                    }
                )
            if "LANG-FR" in chunk_text:
                result["langues"].append(
                    {"nom": "Français", "niveau": "Natif"}
                )
            if "LANG-EN" in chunk_text:
                result["langues"].append(
                    {"nom": "Anglais", "niveau": "C1"}
                )
            if "Python PostgreSQL" in chunk_text:
                result["competences"]["technologies"] = [
                    "Python",
                    "PostgreSQL",
                    "Kafka",
                ]
                result["competences"]["methodologies_et_outils"] = [
                    "Scrum",
                    "Git",
                ]
            return result

        with patch.dict(
            watcher._CONFIG["extraction"],
            {
                "chunk_chars": 450,
                "chunk_overlap_chars": 100,
                "max_chunks": 20,
            },
        ), patch.object(
            watcher,
            "_extract_chunk_json",
            side_effect=extraction_for_chunk,
        ) as extract_chunk:
            merged = watcher._extract_cv_json(source, "synthetic-long.pdf")
            final = watcher._validate_json(merged)
            validate_extraction_quality(source, final)

        self.assertGreater(extract_chunk.call_count, 1)
        self.assertEqual(
            final["informations_personnelles"]["nom_complet"],
            "Candidate SYNTHETIQUE",
        )
        self.assertEqual(
            [item["entreprise"] for item in final["experiences_professionnelles"]],
            ["Alpha", "Beta", "Gamma"],
        )
        self.assertEqual(len(final["projets_realises"]), 1)
        self.assertEqual(len(final["formation"]), 1)
        self.assertEqual(len(final["certifications"]), 1)
        self.assertEqual(
            [item["nom"] for item in final["langues"]],
            ["Français", "Anglais"],
        )


if __name__ == "__main__":
    unittest.main()
