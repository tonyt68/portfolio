import fs from 'fs/promises';
import path from 'path';

export type KnowledgeEntry = {
  question: string;
  answer: string;
  tags: string[];
  source: string;
};

export type KnowledgeBase = {
  entries: KnowledgeEntry[];
};

export async function loadKnowledge(): Promise<KnowledgeBase> {
  const filePath = path.resolve(process.cwd(), 'knowledge', 'knowledge.json');
  const content = await fs.readFile(filePath, 'utf8');
  return JSON.parse(content) as KnowledgeBase;
}

export async function loadRestrictedTopics(): Promise<string[]> {
  const filePath = path.resolve(process.cwd(), 'knowledge', 'restricted-topics.json');
  const content = await fs.readFile(filePath, 'utf8');
  const parsed = JSON.parse(content) as { restricted: string[] };
  return parsed.restricted.map((t) => t.toLowerCase());
}
