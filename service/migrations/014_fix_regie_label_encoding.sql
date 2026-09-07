-- Repair Régie label corrupted when migration 013 was piped via PowerShell
-- (UTF-8 é became literal ??). Uses ASCII-only Unicode escape — safe on all shells.
UPDATE ref.contract_types
SET label_fr = E'R\u00e9gie'
WHERE code = 'Regie'
  AND label_fr <> E'R\u00e9gie';
