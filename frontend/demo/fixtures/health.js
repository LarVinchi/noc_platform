const gib = 1024 ** 3;
const main = 'af614b793d7281c093ae5c0d6e8477b0dc921582';
const previous = 'e78c94051ad2607f3029ec877dd65a30a96f1b42';
export function healthFixture(scenario) {
  const now = new Date().toISOString();
  const stale = scenario === 'Status stale';
  const observed = stale ? new Date(Date.now() - 300000).toISOString() : now;
  const running = scenario === 'Up to date' ? main : previous;
  const failed = scenario === 'Failed', deploying = scenario === 'Deploying', missing = scenario === 'Missing measurements', unhealthy = scenario === 'Unhealthy containers';
  const deployment = { target_sha: main, deployed_sha: running, deployed_at: new Date(Date.now() - 7200000).toISOString(), result: deploying ? 'running' : failed ? 'failed' : 'success', stage: deploying ? 'readiness_check' : failed ? 'readiness_failed' : 'complete', rollback: failed ? 'succeeded' : 'not_required', last_check_at: observed, started_at: new Date(Date.now() - 180000).toISOString(), error_type: failed ? 'readiness_timeout' : null };
  return { hosts: scenario === 'Empty host list' ? [] : [{ host_id: 'afl-noc-01', received_at: observed,
    summary: { state: ['Up to date', 'Update pending', 'Deploying', 'Failed', 'Status stale'].includes(scenario) ? scenario : 'Up to date', application_health: stale || missing ? 'Unknown' : unhealthy ? 'Unhealthy' : 'Healthy', host_fresh: !stale, deployer_fresh: !stale, github_fresh: !stale, running_sha: running, alerts: [], reason: failed ? 'The latest update failed. The previous release remains healthy after rollback.' : deploying ? 'The deployer is checking application readiness for the latest release.' : scenario === 'Update pending' ? 'A tested release is published and waiting for the deployment checker.' : stale ? 'Host evidence has not arrived within the freshness window.' : 'The latest tested release is running on the application server.' },
    report: { observed_at: observed, application_ready: missing ? null : !unhealthy,
      host: { hostname: 'afl-noc-01', distribution: 'Ubuntu', version: '24.04 LTS', kernel: '6.8.0-71-generic', architecture: 'x86_64', cpu_model: 'Intel Xeon · virtual CPU', cpu_cores: 4, uptime_seconds: 1278600 },
      metrics: { cpu_percent: missing ? null : 24.7, memory_used_percent: missing ? null : 58.2, memory_available_bytes: missing ? null : 6.688 * gib, memory_total_bytes: 16 * gib, load: missing ? [null, null, null] : [0.94, 1.12, 1.08], swap_used_bytes: missing ? null : 0, swap_total_bytes: 2 * gib,
        filesystems: [{ mount: '/', used_percent: missing ? null : 42.6, available_bytes: missing ? null : 91.84 * gib, total_bytes: 160 * gib, inode_used_percent: missing ? null : 12.8 }],
        interfaces: [{ name: 'eth0', state: 'up', rx_bytes_per_second: missing ? null : 2400000, tx_bytes_per_second: missing ? null : 860000, rx_errors: 0, tx_errors: 0 }],
        disk_io: [{ device: 'vda', read_bytes_per_second: missing ? null : 320000, write_bytes_per_second: missing ? null : 1240000 }] },
      github: { main_sha: main, build_sha: main, build_result: 'success', release_sha: main, checked_at: observed, error: null }, deployment,
      docker: { available: true, operating_system: 'Docker Engine on Ubuntu', context: 'default', name: 'afl-noc-01', cpus: 4, memory_bytes: 16 * gib },
      containers: ['noc-api', 'noc-frontend', 'noc-postgres'].map((name, i) => ({ name, status: unhealthy && i === 0 ? 'restarting' : 'running', health: unhealthy && i === 0 ? 'unhealthy' : 'healthy', restarts: unhealthy && i === 0 ? 4 : 0, cpu_percent: missing ? null : [8.2, 1.4, 6.1][i], memory_used_bytes: missing ? null : [0.65, 0.12, 1.8][i] * gib, memory_limit_bytes: 4 * gib, revision: i === 2 ? null : running })),
      deployments: [{ ...deployment, attempt_id: 'demo-latest', updated_at: now }, { attempt_id: 'demo-previous', target_sha: previous, result: 'success', stage: 'complete', rollback: 'not_required', started_at: new Date(Date.now() - 7300000).toISOString(), updated_at: new Date(Date.now() - 7200000).toISOString() }],
      collection_errors: missing ? ['cpu_sample_unavailable', 'memory_sample_unavailable', 'filesystem_sample_unavailable'] : [] },
  }] };
}
export function historyFixture(hours = 24, scenario) {
  const count = hours === 1 ? 20 : hours === 168 ? 28 : 24, bucket = hours * 3600 / count;
  return { bucket_seconds: bucket, points: Array.from({ length: count }, (_, i) => ({ time: new Date(Date.now() - (count - 1 - i) * bucket * 1000).toISOString(), samples: 10, cpu_percent: scenario === 'Missing measurements' || i === 9 || i === 10 ? null : 24 + Math.sin(i * 1.3) * 9 + (i % 4) * 3, memory_percent: scenario === 'Missing measurements' || i === 10 ? null : 54 + Math.sin(i / 3) * 4 + i / 5, storage_percent: scenario === 'Missing measurements' || i === 10 ? null : 40 + i / 9 })) };
}
