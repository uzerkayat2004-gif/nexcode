import { Command } from 'commander';
import { loginCommand } from './login.js';
import { logoutCommand } from './logout.js';
import { statusCommand } from './status.js';

export const authCommand = new Command('auth')
  .description('Authentication commands')
  .addCommand(loginCommand)
  .addCommand(logoutCommand)
  .addCommand(statusCommand);
