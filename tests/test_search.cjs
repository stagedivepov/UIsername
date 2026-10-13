const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({window: {}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../ui/search.js'), 'utf8'), context);
const matches = context.window.PlatformSearch.matches;
test('search handles typos, transpositions, missing characters, aliases and accents', () => {
  for (const [name, query] of [['Instagram', 'instagran'], ['Discord', 'discor'], ['GitHub', 'githbu'],
    ['PlayStation', 'psn'], ['Bluesky', 'bsky'], ['YouTube', 'youtub'], ['TikTok', 'tík tok']]) {
    assert.equal(matches(name, query), true, `${name}: ${query}`);
  }
});
test('short searches stay selective and unrelated searches stay empty', () => {
  assert.equal(matches('Steam', 'zz'), false);
  assert.equal(matches('Reddit', 'instagram'), false);
  assert.equal(matches('GitLab', 'git'), true);
  assert.equal(matches('Steam', ''), true);
  assert.equal(matches('Steam', 'z'.repeat(10000)), false);
});
