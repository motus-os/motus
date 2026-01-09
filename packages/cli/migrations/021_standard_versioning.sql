-- Migration: 021_standard_versioning
-- Version: 21
-- Description: Capture standards versions in entity_versions

-- UP

CREATE TRIGGER IF NOT EXISTS standards_version_seed
AFTER INSERT ON standards
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'standard',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'standard' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'name', NEW.name,
            'description', NEW.description,
            'level_key', NEW.level_key,
            'check_type_key', NEW.check_type_key,
            'check_command', NEW.check_command,
            'check_pattern', NEW.check_pattern,
            'threshold_min', NEW.threshold_min,
            'threshold_max', NEW.threshold_max,
            'failure_message', NEW.failure_message,
            'is_blocking', NEW.is_blocking,
            'sort_order', NEW.sort_order,
            'doc_path', NEW.doc_path
        ),
        'system';
END;

CREATE TRIGGER IF NOT EXISTS standards_version_capture
AFTER UPDATE ON standards
WHEN OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'standard',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'standard' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'name', NEW.name,
            'description', NEW.description,
            'level_key', NEW.level_key,
            'check_type_key', NEW.check_type_key,
            'check_command', NEW.check_command,
            'check_pattern', NEW.check_pattern,
            'threshold_min', NEW.threshold_min,
            'threshold_max', NEW.threshold_max,
            'failure_message', NEW.failure_message,
            'is_blocking', NEW.is_blocking,
            'sort_order', NEW.sort_order,
            'doc_path', NEW.doc_path
        ),
        'system';
END;

INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
SELECT
    'standard',
    s.id,
    COALESCE((SELECT MAX(version) FROM entity_versions
              WHERE entity_type = 'standard' AND entity_id = s.id), 0) + 1,
    json_object(
        'name', s.name,
        'description', s.description,
        'level_key', s.level_key,
        'check_type_key', s.check_type_key,
        'check_command', s.check_command,
        'check_pattern', s.check_pattern,
        'threshold_min', s.threshold_min,
        'threshold_max', s.threshold_max,
        'failure_message', s.failure_message,
        'is_blocking', s.is_blocking,
        'sort_order', s.sort_order,
        'doc_path', s.doc_path
    ),
    'system'
FROM standards s
WHERE NOT EXISTS (
    SELECT 1 FROM entity_versions ev
    WHERE ev.entity_type = 'standard' AND ev.entity_id = s.id
);

-- DOWN

DROP TRIGGER IF EXISTS standards_version_capture;
DROP TRIGGER IF EXISTS standards_version_seed;
DELETE FROM entity_versions WHERE entity_type = 'standard';
