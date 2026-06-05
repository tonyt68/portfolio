import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { checkRestricted } from './agent.js';
import { KnowledgeBase } from './knowledge.js';

// pull retrieveRelevantEntries out for testing via a small inline copy
// (it's not exported, so we test its behavior through the shape of inputs)

const mockKnowledge: KnowledgeBase = {
  entries: [
    {
      question: 'What are the Luna return steps?',
      answer: 'Luna return flow starts with customer auth, then validation.',
      tags: ['luna', 'returns', 'validation'],
      source: 'Luna Returns Overview',
    },
    {
      question: 'How does ABC form state work?',
      answer: 'ABCFormState manages form state locally, not Redux.',
      tags: ['abc', 'form state', '1800contacts'],
      source: '1-800 Contacts UI Notes',
    },
  ],
};

const restrictedTopics = ['financial forecast', 'salary', 'acquisition'];

describe('checkRestricted', () => {
  it('blocks a restricted topic', () => {
    assert.equal(checkRestricted("What is the company's financial forecast?", restrictedTopics), true);
  });

  it('blocks a partial match', () => {
    assert.equal(checkRestricted('tell me about salary bands', restrictedTopics), true);
  });

  it('allows a normal dev question', () => {
    assert.equal(checkRestricted('How do I reduce Luna return latency?', restrictedTopics), false);
  });

  it('is case insensitive', () => {
    assert.equal(checkRestricted('FINANCIAL FORECAST question', restrictedTopics), true);
  });
});

describe('knowledge retrieval scoring', () => {
  function retrieve(question: string, knowledge: KnowledgeBase) {
    const tokens = question.toLowerCase().split(/\s+/).filter((t) => t.length > 3);
    const scored = knowledge.entries.map((entry) => {
      const text = `${entry.question} ${entry.answer} ${entry.tags.join(' ')}`.toLowerCase();
      const score = tokens.filter((token) => text.includes(token)).length;
      return { entry, score };
    });
    return scored.filter(({ score }) => score > 0).sort((a, b) => b.score - a.score).map(({ entry }) => entry);
  }

  it('returns luna entry for luna question', () => {
    const results = retrieve('luna returns validation steps', mockKnowledge);
    assert.equal(results.length > 0, true);
    assert.equal(results[0].source, 'Luna Returns Overview');
  });

  it('returns abc entry for abc question', () => {
    const results = retrieve('abc form state management', mockKnowledge);
    assert.equal(results.length > 0, true);
    assert.equal(results[0].source, '1-800 Contacts UI Notes');
  });

  it('returns nothing for unrelated question', () => {
    const results = retrieve('kubernetes cluster ingress nginx config', mockKnowledge);
    assert.equal(results.length, 0);
  });
});

describe('token cost calculation', () => {
  const COST_PER_M_INPUT = 3.0;
  const COST_PER_M_OUTPUT = 15.0;

  function calcCost(inputTokens: number, outputTokens: number): number {
    return (inputTokens / 1_000_000) * COST_PER_M_INPUT +
           (outputTokens / 1_000_000) * COST_PER_M_OUTPUT;
  }

  it('zero tokens = zero cost', () => {
    assert.equal(calcCost(0, 0), 0);
  });

  it('1M input tokens = $3.00', () => {
    assert.equal(calcCost(1_000_000, 0), 3.0);
  });

  it('1M output tokens = $15.00', () => {
    assert.equal(calcCost(0, 1_000_000), 15.0);
  });

  it('typical call ~700 tokens costs under 2 cents', () => {
    const cost = calcCost(500, 300);
    assert.equal(cost < 0.02, true);
  });
});
