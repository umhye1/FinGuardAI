const { test } = require('node:test');
const assert = require('node:assert/strict');
const { validate } = require('./convention.cjs');
const body = '## 개요\n\n## 변경 사항\n\n## 검증\n\n## 관련 이슈\nclose #29\n\n## 리뷰 메모';
const pr = { head: { ref: 'feat/#29-ai-performance-evaluation' }, base: { ref: 'main' }, title: '[#29] AI 평가 구현', body };
test('valid issue-linked branches', () => {
  for (const ref of ['feat/#29', 'fix/#29-ai-runtime', pr.head.ref]) {
    assert.equal(validate({ ...pr, head: { ref } }).number, 29);
  }
});
test('invalid names and mismatching numbers fail', () => {
  for (const ref of ['codex/ai', 'feat/#0', 'feature/#29-ai', 'feat/#28-ai']) {
    assert.throws(() => validate({ ...pr, head: { ref } }));
  }
  assert.throws(() => validate({ ...pr, body: body.replace('close #29', 'close #3') }));
  assert.throws(() => validate({ ...pr, body: body.replace('## 검증', '테스트') }));
  assert.throws(() => validate({ ...pr, title: 'AI 평가' }));
});
test('explicit dev to main release exception only', () => {
  assert.equal(validate({ ...pr, head: { ref: 'dev' }, title: '[Release] 통합 배포' }).release, true);
  assert.throws(() => validate({ ...pr, head: { ref: 'dev' } }));
});
