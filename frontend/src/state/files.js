export function downloadFile(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  // Give browsers time to start the download before releasing its object URL.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function comparisonCsv(result) {
  const header = 'policy,physical_frames,references,hits,faults,replacements,hit_rate,fault_rate,tlb_capacity,tlb_hits,tlb_misses';
  return [header, ...result.rows.map(({ policy, physical_frames, metrics: m, tlb }) =>
    [policy, physical_frames, m.references, m.hits, m.faults, m.replacements, m.hit_rate, m.fault_rate, result.tlb_capacity, tlb?.hits ?? '', tlb?.misses ?? ''].join(','))].join('\r\n') + '\r\n';
}

export function experimentDraft(experiment) {
  return {
    pageSize: String(experiment.config.page_size), virtualPages: String(experiment.config.virtual_pages),
    physicalFrames: String(experiment.config.physical_frames), inputMode: experiment.input_mode,
    policy: experiment.policy, workload: experiment.workload.join(', '),
    tlbCapacity: String(experiment.tlb_capacity),
  };
}
