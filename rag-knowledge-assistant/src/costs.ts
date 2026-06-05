import fs from 'fs/promises';
import path from 'path';

type CostLogEntry = {
  timestamp: string;
  question: string;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
  cacheHit: boolean;
};

type CostLog = {
  totalUsd: number;
  totalCalls: number;
  cacheHits: number;
  entries: CostLogEntry[];
};

const COST_LOG_PATH = path.resolve(process.cwd(), 'cost-log.json');

function formatCost(usd: number): string {
  if (usd === 0) return '$0.0000';
  return `$${usd.toFixed(4)}`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString();
}

function truncate(str: string, len: number): string {
  return str.length > len ? str.slice(0, len - 1) + '…' : str.padEnd(len);
}

async function main() {
  let log: CostLog;
  try {
    const content = await fs.readFile(COST_LOG_PATH, 'utf8');
    log = JSON.parse(content) as CostLog;
  } catch {
    console.log('No cost log found yet. Run some questions first with: npm run ask -- "<question>"');
    process.exit(0);
  }

  if (log.entries.length === 0) {
    console.log('Cost log is empty.');
    process.exit(0);
  }

  const divider = '─'.repeat(90);
  const hitRate = Math.round((log.cacheHits / log.totalCalls) * 100);

  console.log('\n  TonyAI RAG Knowledge Assistant — Token Cost Dashboard');
  console.log(`  Powered by TonyAI · Built with Claude\n`);
  console.log(divider);
  console.log(
    `  ${'#'.padEnd(3)} ${'Time'.padEnd(10)} ${'In'.padStart(6)} ${'Out'.padStart(6)} ${'Cost'.padStart(9)}  ${'Cache'.padEnd(6)}  Question`
  );
  console.log(divider);

  log.entries.forEach((entry, i) => {
    const num = String(i + 1).padEnd(3);
    const time = formatTime(entry.timestamp).padEnd(10);
    const inTok = String(entry.inputTokens).padStart(6);
    const outTok = String(entry.outputTokens).padStart(6);
    const cost = formatCost(entry.costUsd).padStart(9);
    const cache = entry.cacheHit ? 'CACHE' : '     ';
    const question = truncate(entry.question, 42);
    console.log(`  ${num} ${time} ${inTok} ${outTok} ${cost}  ${cache}  ${question}`);
  });

  console.log(divider);
  console.log(`  Total calls : ${log.totalCalls}`);
  console.log(`  Cache hits  : ${log.cacheHits} (${hitRate}%) — these cost $0.00`);
  console.log(`  LLM calls   : ${log.totalCalls - log.cacheHits}`);
  console.log(`  Total cost  : ${formatCost(log.totalUsd)}`);
  console.log(`  Avg per call: ${formatCost(log.totalUsd / (log.totalCalls - log.cacheHits || 1))} (LLM calls only)`);
  console.log(divider);
  console.log(`\n  At scale: every promoted knowledge entry = $0.00 per future hit.`);
  console.log(`  Target cache hit rate 70%+ = costs decline as knowledge base grows.\n`);
}

main().catch((err) => {
  console.error('Error reading cost log:', err);
  process.exit(1);
});
