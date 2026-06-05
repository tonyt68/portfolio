import Anthropic from '@anthropic-ai/sdk';
import { KnowledgeBase, KnowledgeEntry } from './knowledge.js';

let client: Anthropic | null = null;
function getClient(): Anthropic {
  if (!client) client = new Anthropic({
    apiKey: process.env.ANTHROPIC_API_KEY,
    baseURL: process.env.ANTHROPIC_BASE_URL,
  });
  return client;
}

const SYSTEM_PROMPT = `You are the Enterprise internal developer assistant — a trusted, senior-level engineering resource.

Your job is to answer developer questions grounded strictly in the provided knowledge base entries. You reason over the context given, synthesize when multiple entries are relevant, and always point developers to the right files, services, or teams.

Rules:
- Answer only from the provided knowledge base context. Do not invent file names, services, or facts not present in the entries.
- If the knowledge base partially covers the question, answer what you can and clearly state what is not yet documented.
- Be specific and actionable — name files, services, and steps when the context includes them.
- Keep answers tight. Developers are busy. No fluff.
- If nothing in the knowledge base is relevant, say so honestly and suggest where to look (Confluence, Slack, team lead).
- Never hallucinate Enterprise-specific internal details not present in the context.
- Plain text output only — no markdown, no headers, no bold, no tables, no bullet symbols. Use numbered steps and plain indentation. This output renders in a terminal.
- Do not add testing advice, warnings, or caveats unless the question specifically asks about testing.`;

const RESTRICTED_RESPONSE =
  "I'm not authorized to provide information on that topic. Please contact the appropriate team directly.";

export function checkRestricted(question: string, restrictedTopics: string[]): boolean {
  const lower = question.toLowerCase();
  return restrictedTopics.some((topic) => lower.includes(topic));
}

function formatKnowledgeContext(entries: KnowledgeEntry[]): string {
  if (entries.length === 0) return 'No relevant knowledge base entries found.';
  return entries
    .map(
      (e, i) =>
        `[Entry ${i + 1}]\nSource: ${e.source}\nQ: ${e.question}\nA: ${e.answer}`
    )
    .join('\n\n');
}

function retrieveRelevantEntries(question: string, knowledge: KnowledgeBase): KnowledgeEntry[] {
  const tokens = question
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 3);

  const scored = knowledge.entries.map((entry) => {
    const text = `${entry.question} ${entry.answer} ${entry.tags.join(' ')}`.toLowerCase();
    const score = tokens.filter((token) => text.includes(token)).length;
    return { entry, score };
  });

  return scored
    .filter(({ score }) => score >= 2)
    .sort((a, b) => b.score - a.score)
    .map(({ entry }) => entry);
}

// Sonnet 4.6 pricing per million tokens
const COST_PER_M_INPUT = 3.0;
const COST_PER_M_OUTPUT = 15.0;

export type TokenUsage = {
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
  cacheHit: boolean;
};

export type AnswerResult = {
  text: string;
  sources: string[];
  usage: TokenUsage;
};

export async function answerQuestion(
  question: string,
  knowledge: KnowledgeBase,
  restrictedTopics: string[] = []
): Promise<AnswerResult> {
  if (checkRestricted(question, restrictedTopics)) {
    return {
      text: RESTRICTED_RESPONSE,
      sources: ['restricted-topics.json'],
      usage: { inputTokens: 0, outputTokens: 0, costUsd: 0, cacheHit: true },
    };
  }

  const relevantEntries = retrieveRelevantEntries(question, knowledge);
  const context = formatKnowledgeContext(relevantEntries);
  const userMessage = `Knowledge base context:\n\n${context}\n\n---\n\nDeveloper question: ${question}`;

  const message = await getClient().messages.create({
    model: process.env.ANTHROPIC_MODEL!,
    max_tokens: 1024,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userMessage }],
  });

  const text = message.content
    .filter((block) => block.type === 'text')
    .map((block) => (block as { type: 'text'; text: string }).text)
    .join('\n');

  const sources =
    relevantEntries.length > 0
      ? relevantEntries.map((e) => e.source)
      : ['no matching knowledge base entry — Claude answered from general context'];

  const inputTokens = message.usage.input_tokens;
  const outputTokens = message.usage.output_tokens;
  const costUsd = (inputTokens / 1_000_000) * COST_PER_M_INPUT +
                  (outputTokens / 1_000_000) * COST_PER_M_OUTPUT;

  return {
    text,
    sources,
    usage: { inputTokens, outputTokens, costUsd, cacheHit: false },
  };
}
