import { Command } from 'commander';
import chalk from 'chalk';
import { clearAuth } from '../utils/auth.js';

export const logoutCommand = new Command('logout')
  .description('Sign out of NexCode')
  .action(async () => {
    try {
      await clearAuth();
      console.log(chalk.green('Signed out successfully'));
    } catch (error) {
      console.error(chalk.red('Failed to sign out'));
      process.exit(1);
    }
  });
