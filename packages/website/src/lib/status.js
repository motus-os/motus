import statusSystem from '../data/status-system.json';

const statuses = statusSystem?.statuses || {};
const origins = statusSystem?.origins || {};

export const getStatusLabel = (status, fallback = 'Current') =>
  statuses?.[status]?.label || fallback;

export const getStatusClass = (status, kind = 'chip') => {
  const base = kind === 'badge' ? 'status-badge' : 'status-chip';
  const css = statuses?.[status]?.css_class || 'status-current';
  return `${base} ${css}`.trim();
};

export const getOriginLabel = (origin) => origins?.[origin]?.label || '';

export const getOriginClass = (origin, kind = 'chip') => {
  if (!origin) return '';
  const base = kind === 'badge' ? 'status-badge' : 'status-chip';
  const css = origin === 'external' ? 'status-external' : 'status-current';
  return `${base} ${css}`.trim();
};

export const getDisplayBadge = ({ status, origin, kind = 'chip' }) => {
  if (origin === 'external') {
    return {
      label: getOriginLabel(origin) || 'External',
      className: getOriginClass(origin, kind),
    };
  }
  return {
    label: getStatusLabel(status),
    className: getStatusClass(status, kind),
  };
};
