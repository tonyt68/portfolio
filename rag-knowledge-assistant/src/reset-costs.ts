import fs from 'fs/promises';
import path from 'path';

const COST_LOG_PATH = path.resolve(process.cwd(), 'cost-log.json');

async function main() {
  await fs.writeFile(COST_LOG_PATH, JSON.stringify(
    { totalUsd: 0, totalCalls: 0, cacheHits: 0, entries: [] },
    null, 2
  ));
  console.log('Cost log reset. Ready for demo.');
}

main();
