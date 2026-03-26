import { Command } from 'commander';
import chalk from 'chalk';
import { getAuth } from '../utils/auth.js';

export const statusCommand = new Command('status')
  .description('Check authentication status')
  .action(async () => {
    const auth = await getAuth();

    if (!auth) {
      console.log(chalk.yellow('Not authenticated'));
      console.log(chalk.gray('Run "nexcode auth login" to sign in'));
      return;
    }

    console.log(chalk.green('Authenticated'));
    console.log(chalk.gray(`Email: ${auth.email}`));
    console.log(chalk.gray(`Auth type: ${auth.type}`));
  });
