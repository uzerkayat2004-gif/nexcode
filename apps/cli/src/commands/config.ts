import { Command } from 'commander';
import chalk from 'chalk';
import { getConfig, setConfig, listConfig } from '../utils/config.js';

export const configCommand = new Command('config')
  .description('Manage NexCode configuration')
  .addCommand(
    new Command('get')
      .description('Get a config value')
      .argument('<key>', 'Config key')
      .action(async (key) => {
        const value = await getConfig(key);
        if (value === undefined) {
          console.log(chalk.yellow(`Config key "${key}" not found`));
        } else {
          console.log(value);
        }
      })
  )
  .addCommand(
    new Command('set')
      .description('Set a config value')
      .argument('<key>', 'Config key')
      .argument('<value>', 'Config value')
      .action(async (key, value) => {
        await setConfig(key, value);
        console.log(chalk.green(`Set ${key} = ${value}`));
      })
  )
  .addCommand(
    new Command('list')
      .description('List all config values')
      .action(async () => {
        const config = await listConfig();
        for (const [key, value] of Object.entries(config)) {
          console.log(`${chalk.cyan(key)}: ${value}`);
        }
      })
  );
