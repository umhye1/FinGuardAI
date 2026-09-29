const sections = ['개요', '변경 사항', '검증', '관련 이슈', '리뷰 메모'];

function validate(pr) {
  // Integration branches are explicitly reserved; feature branches always need an issue.
  if (pr.head.ref === 'dev' && pr.base.ref === 'main') {
    if (!/^\[Release\] \S.+/.test(pr.title)) throw Error('릴리스 제목: [Release] 설명');
    return { release: true };
  }
  const branch = /^(feat|fix)\/#([1-9]\d*)(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$/.exec(pr.head.ref);
  if (!branch) throw Error('브랜치: feat/#번호[-설명] 또는 fix/#번호[-설명]');
  const title = /^\[#([1-9]\d*)\] \S.+/.exec(pr.title);
  if (!title || title[1] !== branch[2]) throw Error('브랜치와 PR 제목의 이슈 번호가 달라요.');
  const body = pr.body || '';
  const closes = [...body.matchAll(/^\s*(?:close|closes|closed)\s+#([1-9]\d*)\s*$/gim)];
  if (!closes.some(m => m[1] === branch[2])) throw Error(`관련 이슈에 close #${branch[2]}를 작성하세요.`);
  for (const section of sections) {
    if (!body.split(/\r?\n/).some(line => line.trim() === `## ${section}`)) {
      throw Error(`PR 템플릿의 '## ${section}' 항목이 필요합니다.`);
    }
  }
  return { number: Number(branch[2]), type: branch[1], release: false };
}
module.exports = { validate };
