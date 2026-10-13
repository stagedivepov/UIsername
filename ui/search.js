(() => {
  'use strict';
  const aliases = {xtwitter: ['x', 'twitter'], chesscom: ['chess', 'chess.com'], minecraft: ['mine craft'], playstation: ['psn', 'ps', 'play station'], instagram: ['insta', 'instagram'],
    youtube: ['yt', 'you tube'], github: ['git hub'], gitlab: ['git lab'],
    tiktok: ['tik tok'], telegram: ['tg'], bluesky: ['bsky', 'blue sky']};
  const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');
  function distance(a, b) {
    const rows = Array.from({length: a.length + 1}, () => Array(b.length + 1).fill(0));
    for (let i = 0; i <= a.length; i++) rows[i][0] = i;
    for (let j = 0; j <= b.length; j++) rows[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
      rows[i][j] = Math.min(rows[i-1][j] + 1, rows[i][j-1] + 1, rows[i-1][j-1] + (a[i-1] !== b[j-1]));
      if (i > 1 && j > 1 && a[i-1] === b[j-2] && a[i-2] === b[j-1]) rows[i][j] = Math.min(rows[i][j], rows[i-2][j-2] + 1);
    }
    return rows[a.length][b.length];
  }
  function matches(name, input) {
    const query = normalize(input).slice(0, 64), target = normalize(name);
    if (!query) return true;
    const limit = query.length < 3 ? 0 : query.length <= 5 ? 1 : 2;
    return [target, ...(aliases[target] || []).map(normalize)].some(candidate => {
      if (candidate.includes(query)) return true;
      if (!limit) return false;
      if (distance(query, candidate) <= limit) return true;
      return query.length < candidate.length && [-1, 0, 1].some(offset =>
        distance(query, candidate.slice(0, query.length + offset)) <= limit);
    });
  }
  window.PlatformSearch = {matches};
})();
