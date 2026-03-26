import { Command } from 'commander';
import chalk from 'chalk';
import { getAuth } from '../utils/auth.js';

export const chatCommand = new Command('chat')
  .description('Start a chat session with AI')
  .option('-p, --provider <provider>', 'AI provider to use')
  .option('-m, --model <model>', 'Model to use')
  .option('-s, --system <prompt>', 'System prompt')
  .action(async (options) => {
    const auth = await getAuth();

    if (!auth) {
      console.error(chalk.red('Not authenticated. Run "nexcode auth login" first.'));
      process.exit(1);
    }

    console.log(chalk.cyan('Starting chat session...'));
    console.log(chalk.gray(`Provider: ${options.provider || 'default'}`));
    console.log(chalk.gray(`Model: ${options.model || 'default'}`));
    console.log('');

    // TODO: Implement chat with React Ink UI
    console.log(chalk.yellow('Chat UI coming soon!'));
  });
