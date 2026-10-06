// La clave ONPE mantiene sus ceros iniciales; no equivale al ubigeo INEI.
export const LIMA_METROPOLITANA = '140100';
export const normalize = text => String(text ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
export const rankOrganizations = record => [...(record?.organizations || [])].sort((a, b) => b.votes - a.votes || a.organization.localeCompare(b.organization, 'es'));
// A downloaded cut with zero valid votes has no electoral leader.
export const leadingOrganizations = record => record?.valid_votes > 0 ? rankOrganizations(record) : [];
export function districtCoverage(data, {department = '', province = '', search = '', scope = ''} = {}) {
  const records = new Map(data.records.filter(r => r.level === 'distrital').map(r => [r.key, r]));
  const q = normalize(search);
  return data.coverage.filter(t => t.level === 'distrital' && (!scope || t.province_code === scope) && (!department || t.department === department) && (!province || t.province_code === province))
    .map(t => ({...t, record: records.get(t.key) || null}))
    .filter(t => !q || normalize([t.department, t.province, t.district, ...(t.record?.organizations || []).map(o => o.organization)].join(' ')).includes(q))
    .sort((a, b) => (a.department + ' ' + a.province + ' ' + a.district).localeCompare(b.department + ' ' + b.province + ' ' + b.district, 'es'));
}
export function metropolitanRecord(data) {return data.records.find(r => r.level === 'provincial' && r.ubigeo === LIMA_METROPOLITANA) || null;}
export function coverageCounts(rows) {return {downloaded: rows.filter(r => r.record).length, pending: rows.filter(r => r.status === 'pending').length, not_applicable: rows.filter(r => r.status === 'not_applicable').length};}
