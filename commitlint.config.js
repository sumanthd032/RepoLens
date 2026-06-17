// Enforces Conventional Commits (feat, fix, test, docs, refactor, chore, style, perf).
// Used by the commitlint pre-commit hook on the commit-msg stage.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'test', 'docs', 'refactor', 'chore', 'style', 'perf', 'ci', 'build', 'revert'],
    ],
  },
};
