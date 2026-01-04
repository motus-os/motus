export const validatePatterns = (patterns) => {
  const allowedStatuses = new Set(['verified', 'building', 'target']);

  for (const pattern of patterns) {
    if (!pattern.id) {
      throw new Error('Implementation pattern missing id.');
    }
    if (!allowedStatuses.has(pattern.status)) {
      throw new Error(`Implementation pattern ${pattern.id} has invalid status.`);
    }
    if (!pattern.title || !pattern.summary || !pattern.what || !pattern.why) {
      throw new Error(`Implementation pattern ${pattern.id} missing required fields.`);
    }
    if (!Array.isArray(pattern.how) || pattern.how.length === 0) {
      throw new Error(`Implementation pattern ${pattern.id} missing how steps.`);
    }
    if (!pattern.quick) {
      throw new Error(`Implementation pattern ${pattern.id} missing quick reference.`);
    }
  }
};
