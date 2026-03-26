import { Command } from 'commander';
import { authCommand } from './commands/auth.js';
import { chatCommand } from './commands/chat.js';
import { configCommand } from './commands/config.js';
import { version } from './utils/version.js';

const program = new Command();

program
  .name('nexcode')
  .description('AI-powered coding assistant - Claude Code for everyone')
  .version(version);

program.addCommand(authCommand);
program.addCommand(chatCommand);
program.addCommand(configCommand);

program.parse();
