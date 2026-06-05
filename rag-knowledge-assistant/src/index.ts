import dotenv from 'dotenv';
import fs from 'fs/promises';
import path from 'path';
import { loadKnowledge, loadRestrictedTopics } from './knowledge.js';
import { answerQuestion, TokenUsage } from './agent.js';

dotenv.config({ override: true });

const REQUIRED_ENV_VARS = ['ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL'];

for (const key of REQUIRED_ENV_VARS) {
  if (!process.env[key]) {
    console.error(`Missing required environment variable: ${key}`);
    console.error('Copy .env.example to .env and set all required values.');
    console.error('  ANTHROPIC_API_KEY  — your Anthropic API key');
    console.error('  ANTHROPIC_MODEL    — e.g. claude-haiku-4-5-20251001 or claude-sonnet-4-6');
    process.exit(1);
  }
}

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

async function loadCostLog(): Promise<CostLog> {
  try {
    const content = await fs.readFile(COST_LOG_PATH, 'utf8');
    return JSON.parse(content) as CostLog;
  } catch {
    return { totalUsd: 0, totalCalls: 0, cacheHits: 0, entries: [] };
  }
}

async function appendCostLog(question: string, usage: TokenUsage): Promise<CostLog> {
  const log = await loadCostLog();
  log.entries.push({
    timestamp: new Date().toISOString(),
    question,
    inputTokens: usage.inputTokens,
    outputTokens: usage.outputTokens,
    costUsd: usage.costUsd,
    cacheHit: usage.cacheHit,
  });
  log.totalUsd += usage.costUsd;
  log.totalCalls += 1;
  if (usage.cacheHit) log.cacheHits += 1;
  await fs.writeFile(COST_LOG_PATH, JSON.stringify(log, null, 2));
  return log;
}

function formatCost(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.001) return `$${(usd * 100).toFixed(4)}¢`;
  return `$${usd.toFixed(4)}`;
}

function printCostSummary(usage: TokenUsage, log: CostLog): void {
  const line = '─'.repeat(50);
  console.log(`\n${line}`);
  if (usage.cacheHit) {
    console.log('  Token cost:    $0.00  (cache hit — no LLM call)');
  } else {
    console.log(`  This call:     ${usage.inputTokens} in + ${usage.outputTokens} out = ${formatCost(usage.costUsd)}`);
  }
  const hitRate = log.totalCalls > 0
    ? Math.round((log.cacheHits / log.totalCalls) * 100)
    : 0;
  console.log(`  Session total: ${log.totalCalls} calls | ${formatCost(log.totalUsd)} | ${hitRate}% cache hits`);
  console.log(line);
}

async function main() {
  const question = process.argv.slice(2).join(' ').trim();

  if (!question) {
    console.error('Usage: npm run ask -- "<your question>"');
    process.exit(1);
  }

  const dailyCap = parseFloat(process.env.COST_DAILY_CAP_USD ?? '1.00');
  const currentLog = await loadCostLog();
  if (currentLog.totalUsd >= dailyCap) {
    console.error(`\n  ⚠ Daily spend cap reached: ${formatCost(currentLog.totalUsd)} of ${formatCost(dailyCap)} limit.`);
    console.error(`  LLM calls blocked. Run \`npm run costs:reset\` to reset or raise COST_DAILY_CAP_USD in .env.\n`);
    process.exit(1);
  }
  if (currentLog.totalUsd >= dailyCap * 0.8) {
    console.warn(`\n  ⚠ Warning: ${formatCost(currentLog.totalUsd)} spent — approaching daily cap of ${formatCost(dailyCap)}.\n`);
  }

  const [knowledge, restrictedTopics] = await Promise.all([loadKnowledge(), loadRestrictedTopics()]);
  const response = await answerQuestion(question, knowledge, restrictedTopics);

  const green = '\x1b[32m';
  const reset = '\x1b[0m';

  console.log(`\nQuestion: ${question}\n`);
  console.log('Answer:');
  console.log(`${green}${response.text}${reset}`);
  if (response.sources.length > 0 && response.sources[0] !== 'no matching knowledge base entry — Claude answered from general context') {
    console.log('\nSources:');
    response.sources.forEach((source) => console.log(`- ${source}`));
  }

  await appendCostLog(question, response.usage);
}

main().catch((error) => {
  console.error('Unexpected error:', error);
  process.exit(1);
});
