import tseslint from 'typescript-eslint';
import { n8nCommunityNodesPlugin } from '@n8n/eslint-plugin-community-nodes';

export default [
	{ ignores: ['dist/**', 'node_modules/**', 'scripts/**', 'eslint.config.mjs'] },
	{ files: ['**/*.ts'], languageOptions: { parser: tseslint.parser } },
	n8nCommunityNodesPlugin.configs.recommended,
	{ files: ['package.json'], languageOptions: { parser: tseslint.parser } },
];
